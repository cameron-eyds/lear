# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The unique worker functionality for this service is contained here.

The entry-point is the **cb_subscription_handler**

The design and flow leverage a few constraints that are placed upon it
by NATS Streaming and using AWAIT on the default loop.
- NATS streaming queues require one message to be processed at a time.
- AWAIT on the default loop effectively runs synchronously

If these constraints change, the use of Flask-SQLAlchemy would need to change.
Flask-SQLAlchemy currently allows the base model to be changed, or reworking
the model to a standalone SQLAlchemy usage with an async engine would need
to be pursued.
"""
import json
import os
import uuid
from typing import Dict

import nats
from entity_queue_common.messages import publish_email_message
from entity_queue_common.service import QueueServiceManager
from entity_queue_common.service_utils import FilingException, QueueException, logger
from flask import Flask
from legal_api import db
from legal_api.core import Filing as FilingCore
from legal_api.models import Business, Filing
from legal_api.services.bootstrap import AccountService
from legal_api.utils.datetime import datetime
from sentry_sdk import capture_message
from sqlalchemy.exc import OperationalError
from sqlalchemy_continuum import versioning_manager

from entity_filer import config
from entity_filer.filing_meta import FilingMeta, json_serial
from entity_filer.filing_processors import (
    admin_freeze,
    alteration,
    annual_report,
    change_of_address,
    change_of_directors,
    change_of_name,
    change_of_registration,
    consent_continuation_out,
    continuation_out,
    conversion,
    correction,
    court_order,
    dissolution,
    incorporation_filing,
    put_back_on,
    registrars_notation,
    registrars_order,
    registration,
    restoration,
    special_resolution,
    transition,
)
from entity_filer.filing_processors.filing_components import name_request


qsm = QueueServiceManager()  # pylint: disable=invalid-name
APP_CONFIG = config.get_named_config(os.getenv('DEPLOYMENT_ENV', 'production'))
FLASK_APP = Flask(__name__)
FLASK_APP.config.from_object(APP_CONFIG)
db.init_app(FLASK_APP)


def get_filing_types(legal_filings: dict):
    """Get the filing type fee codes for the filing.

    Returns: {
        list: a list of filing types.
    }
    """
    filing_types = []
    for k in legal_filings['filing'].keys():
        if Filing.FILINGS.get(k, None):
            filing_types.append(k)
    return filing_types


async def publish_event(business: Business, filing: Filing):
    """Publish the filing message onto the NATS filing subject."""
    try:
        payload = {
            'specversion': '1.x-wip',
            'type': 'bc.registry.business.' + filing.filing_type,
            'source': ''.join([
                APP_CONFIG.LEGAL_API_URL,
                '/business/',
                business.identifier,
                '/filing/',
                str(filing.id)]),
            'id': str(uuid.uuid4()),
            'time': datetime.utcnow().isoformat(),
            'datacontenttype': 'application/json',
            'identifier': business.identifier,
            'data': {
                'filing': {
                    'header': {'filingId': filing.id,
                               'effectiveDate': filing.effective_date.isoformat()
                               },
                    'business': {'identifier': business.identifier},
                    'legalFilings': get_filing_types(filing.filing_json)
                }
            }
        }
        if filing.temp_reg:
            payload['tempidentifier'] = filing.temp_reg
        subject = APP_CONFIG.ENTITY_EVENT_PUBLISH_OPTIONS['subject']
        await qsm.service.publish(subject, payload)
    except Exception as err:  # pylint: disable=broad-except; we don't want to fail out the filing, so ignore all.
        capture_message('Queue Publish Event Error: filing.id=' + str(filing.id) + str(err), level='error')
        logger.error('Queue Publish Event Error: filing.id=%s', filing.id, exc_info=True)


async def process_filing(filing_msg: Dict, flask_app: Flask):  # pylint: disable=too-many-branches,too-many-statements
    """Render the filings contained in the submission.

    Start the migration to using core/Filing
    """
    if not flask_app:
        raise QueueException('Flask App not available.')

    with flask_app.app_context():
        # filing_submission = Filing.find_by_id(filing_msg['filing']['id'])
        filing_core_submission = FilingCore.find_by_id(filing_msg['filing']['id'])

        if not filing_core_submission:
            raise QueueException

        filing_submission = filing_core_submission.storage

        if filing_core_submission.status == Filing.Status.COMPLETED:
            logger.warning('QueueFiler: Attempting to reprocess business.id=%s, filing.id=%s filing=%s',
                           filing_submission.business_id, filing_submission.id, filing_msg)
            return None, None

        # convenience flag to set that the envelope is a correction
        is_correction = filing_core_submission.filing_type == FilingCore.FilingTypes.CORRECTION

        if legal_filings := filing_core_submission.legal_filings():
            uow = versioning_manager.unit_of_work(db.session)
            transaction = uow.create_transaction(db.session)

            business = Business.find_by_internal_id(filing_submission.business_id)

            filing_meta = FilingMeta(application_date=filing_submission.effective_date,
                                     legal_filings=[item for sublist in
                                                    [list(x.keys()) for x in legal_filings]
                                                    for item in sublist])
            if is_correction:
                filing_meta.correction = {}

            for filing in legal_filings:
                if filing.get('alteration'):
                    alteration.process(business, filing_submission, filing, filing_meta, is_correction)

                elif filing.get('annualReport'):
                    annual_report.process(business, filing, filing_meta)

                elif filing.get('changeOfAddress'):
                    change_of_address.process(business, filing, filing_meta)

                elif filing.get('changeOfDirectors'):
                    filing['colinIds'] = filing_submission.colin_event_ids
                    change_of_directors.process(business, filing, filing_meta)

                elif filing.get('changeOfName'):
                    change_of_name.process(business, filing, filing_meta)

                elif filing.get('dissolution'):
                    dissolution.process(business, filing, filing_submission, filing_meta)

                elif filing.get('incorporationApplication'):
                    business, filing_submission, filing_meta = incorporation_filing.process(business,
                                                                                            filing_core_submission.json,
                                                                                            filing_submission,
                                                                                            filing_meta)

                elif filing.get('registration'):
                    business, filing_submission, filing_meta = registration.process(business,
                                                                                    filing_core_submission.json,
                                                                                    filing_submission,
                                                                                    filing_meta)

                elif filing.get('conversion'):
                    business, filing_submission = conversion.process(business,
                                                                     filing_core_submission.json,
                                                                     filing_submission,
                                                                     filing_meta)

                elif filing.get('courtOrder'):
                    court_order.process(business, filing_submission, filing, filing_meta)

                elif filing.get('registrarsNotation'):
                    registrars_notation.process(filing_submission, filing, filing_meta)

                elif filing.get('registrarsOrder'):
                    registrars_order.process(filing_submission, filing, filing_meta)

                elif filing.get('correction'):
                    filing_submission = correction.process(filing_submission, filing, filing_meta, business)

                elif filing.get('transition'):
                    filing_submission = transition.process(business, filing_submission, filing, filing_meta)

                elif filing.get('changeOfRegistration'):
                    change_of_registration.process(business, filing_submission, filing, filing_meta)

                elif filing.get('putBackOn'):
                    put_back_on.process(business, filing, filing_submission, filing_meta)

                elif filing.get('restoration'):
                    restoration.process(business, filing, filing_submission, filing_meta)

                elif filing.get('adminFreeze'):
                    admin_freeze.process(business, filing, filing_submission, filing_meta)

                elif filing.get('consentContinuationOut'):
                    consent_continuation_out.process(business, filing_submission, filing, filing_meta)

                elif filing.get('continuationOut'):
                    continuation_out.process(business, filing_submission, filing, filing_meta)

                if filing.get('specialResolution'):
                    special_resolution.process(business, filing, filing_submission)

            filing_submission.transaction_id = transaction.id

            business_type = business.legal_type if business else filing_submission['business']['legal_type']
            filing_submission.set_processed(business_type)

            filing_submission._meta_data = json.loads(  # pylint: disable=W0212
                json.dumps(filing_meta.asjson, default=json_serial)
            )

            db.session.add(business)
            db.session.add(filing_submission)
            db.session.commit()

            # post filing changes to other services
            if any('dissolution' in x for x in legal_filings):
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type,
                    state=Business.State.HISTORICAL.name
                )

            if any('putBackOn' in x for x in legal_filings):
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type,
                    state=Business.State.ACTIVE.name
                )

            if filing_core_submission.filing_type == FilingCore.FilingTypes.RESTORATION:
                restoration.post_process(business, filing_submission)
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type,
                    state=Business.State.ACTIVE.name
                )

            if any('alteration' in x for x in legal_filings):
                alteration.post_process(business, filing_submission, is_correction)
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type
                )

            if any('changeOfRegistration' in x for x in legal_filings):
                change_of_registration.post_process(business, filing_submission)
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type
                )

            if business.legal_type in ['SP', 'GP', 'BC', 'BEN', 'CC', 'ULC', 'CP'] and \
                    any('correction' in x for x in legal_filings):
                correction.post_process(business, filing_submission)
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type
                )

            if any('incorporationApplication' in x for x in legal_filings):
                filing_submission.business_id = business.id
                db.session.add(filing_submission)
                db.session.commit()
                incorporation_filing.update_affiliation(business, filing_submission)
                name_request.consume_nr(business, filing_submission)
                incorporation_filing.post_process(business, filing_submission)
                try:
                    await publish_email_message(
                        qsm, APP_CONFIG.EMAIL_PUBLISH_OPTIONS['subject'], filing_submission, 'mras')
                except Exception as err:  # pylint: disable=broad-except, unused-variable # noqa F841;
                    # mark any failure for human review
                    capture_message(
                        f'Queue Error: Failed to place email for filing:{filing_submission.id}'
                        f'on Queue with error:{err}',
                        level='error'
                    )

            if any('registration' in x for x in legal_filings):
                filing_submission.business_id = business.id
                db.session.add(filing_submission)
                db.session.commit()
                registration.update_affiliation(business, filing_submission)
                name_request.consume_nr(business, filing_submission, 'registration')
                registration.post_process(business, filing_submission)

            if any('changeOfName' in x for x in legal_filings):
                change_of_name.post_process(business, filing_submission)

            if any('conversion' in x for x in legal_filings):
                filing_submission.business_id = business.id
                db.session.add(filing_submission)
                db.session.commit()
                conversion.post_process(business, filing_submission)

            try:
                await publish_email_message(
                    qsm, APP_CONFIG.EMAIL_PUBLISH_OPTIONS['subject'], filing_submission, filing_submission.status)
            except Exception as err:  # pylint: disable=broad-except, unused-variable # noqa F841;
                # mark any failure for human review
                capture_message(
                    f'Queue Error: Failed to place email for filing:{filing_submission.id}'
                    f'on Queue with error:{err}',
                    level='error'
                )

            try:
                await publish_event(business, filing_submission)
            except Exception as err:  # pylint: disable=broad-except, unused-variable # noqa F841;
                # mark any failure for human review
                print(err)
                capture_message(
                    f'Queue Error: Failed to publish event for filing:{filing_submission.id}'
                    f'on Queue with error:{err}',
                    level='error'
                )


async def cb_subscription_handler(msg: nats.aio.client.Msg):
    """Use Callback to process Queue Msg objects."""
    try:
        logger.info('Received raw message seq:%s, data=  %s', msg.sequence, msg.data.decode())
        filing_msg = json.loads(msg.data.decode('utf-8'))
        logger.debug('Extracted filing msg: %s', filing_msg)
        await process_filing(filing_msg, FLASK_APP)
    except OperationalError as err:
        logger.error('Queue Blocked - Database Issue: %s', json.dumps(filing_msg), exc_info=True)
        raise err  # We don't want to handle the error, as a DB down would drain the queue
    except FilingException as err:
        logger.error('Queue Error - cannot find filing: %s'
                     '\n\nThis message has been put back on the queue for reprocessing.',
                     json.dumps(filing_msg), exc_info=True)
        raise err  # we don't want to handle the error, so that the message gets put back on the queue
    except (QueueException, Exception):  # pylint: disable=broad-except
        # Catch Exception so that any error is still caught and the message is removed from the queue
        capture_message('Queue Error:' + json.dumps(filing_msg), level='error')
        logger.error('Queue Error: %s', json.dumps(filing_msg), exc_info=True)
