# Copyright © 2020 Province of British Columbia
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
"""Searching on a namerequest.

Provides a proxy endpoint to retrieve name request data.
"""
from http import HTTPStatus
from flask import abort, current_app, jsonify, make_response
from flask_restx import Namespace, Resource, cors

from legal_api.services import namex
from legal_api.utils.util import cors_preflight


API = Namespace('NameRequest', description='NameRequest')


@cors_preflight('GET')
@API.route('/<string:identifier>', methods=['GET', 'OPTIONS'])
class NameRequest(Resource):
    """Proxied name request to namex-api."""

    @staticmethod
    @cors.crossdomain(origin='*')
    def get(identifier):
        """Return a JSON object with name request information."""
        try:
            nr_response = namex.query_nr_number(identifier)

            # Override api response to return a 404 if NR is not found
            if hasattr(nr_response, 'status_code'):
                if nr_response.status_code == HTTPStatus.NOT_FOUND:
                    return make_response(jsonify(message='{} not found.'.format(identifier)), HTTPStatus.NOT_FOUND)

            return nr_response
        except Exception as err:
            current_app.logger.error(err)
            abort(500)
            return {}, 500  # to appease the linter
