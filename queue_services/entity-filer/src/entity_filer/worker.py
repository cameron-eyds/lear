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
from legal_api.models import Business, Filing
from legal_api.services.bootstrap import AccountService
from legal_api.utils.datetime import datetime
from sentry_sdk import capture_message
from sqlalchemy.exc import OperationalError
from sqlalchemy_continuum import versioning_manager

from entity_filer import config
from entity_filer.filing_processors import (
    alteration,
    annual_report,
    change_of_address,
    change_of_directors,
    change_of_name,
    correction,
    incorporation_filing,
    transition,
    voluntary_dissolution,
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
    """Render the filings contained in the submission."""
    if not flask_app:
        raise QueueException('Flask App not available.')

    with flask_app.app_context():
        filing_submission = Filing.find_by_id(filing_msg['filing']['id'])

        if not filing_submission:
            raise QueueException

        if filing_submission.status == Filing.Status.COMPLETED.value:
            logger.warning('QueueFiler: Attempting to reprocess business.id=%s, filing.id=%s filing=%s',
                           filing_submission.business_id, filing_submission.id, filing_msg)
            return None, None

        if legal_filings := filing_submission.legal_filings():
            uow = versioning_manager.unit_of_work(db.session)
            transaction = uow.create_transaction(db.session)

            business = Business.find_by_internal_id(filing_submission.business_id)

            for filing in legal_filings:
                if filing.get('alteration'):
                    alteration.process(business, filing_submission, filing)

                if filing.get('annualReport'):
                    annual_report.process(business, filing)

                elif filing.get('changeOfAddress'):
                    change_of_address.process(business, filing)

                elif filing.get('changeOfDirectors'):
                    filing['colinIds'] = filing_submission.colin_event_ids
                    change_of_directors.process(business, filing)

                elif filing.get('changeOfName'):
                    change_of_name.process(business, filing)

                elif filing.get('voluntaryDissolution'):
                    voluntary_dissolution.process(business, filing)

                elif filing.get('incorporationApplication'):
                    business, filing_submission = incorporation_filing.process(business, filing, filing_submission)

                if filing.get('correction'):
                    filing_submission = correction.process(filing_submission, filing)

                if filing.get('transition'):
                    filing_submission = transition.process(business, filing_submission, filing)

            filing_submission.transaction_id = transaction.id
            filing_submission.set_processed()

            db.session.add(business)
            db.session.add(filing_submission)
            db.session.commit()

            # post filing changes to other services
            if any('alteration' in x for x in legal_filings):
                if name_request.has_new_nr_for_alteration(business, filing_submission.filing_json):
                    name_request.consume_nr(business, filing_submission, '/filing/alteration/nameRequest/nrNumber')
                alteration.post_process(business, filing_submission)
                db.session.add(business)
                db.session.commit()
                AccountService.update_entity(
                    business_registration=business.identifier,
                    business_name=business.legal_name,
                    corp_type_code=business.legal_type
                )

            if any('incorporationApplication' in x for x in legal_filings):
                if any('correction' in x for x in legal_filings):
                    if name_request.has_new_nr_for_correction(filing_submission.filing_json):
                        name_request.consume_nr(business, filing_submission)
                else:
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
