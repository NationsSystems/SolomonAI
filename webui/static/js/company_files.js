/* -------------------------------------------------------------------
   FILE: company_files.js
   DIRECTORY: webui/static/js/
   -------------------------------------------------------------------
   Compatibility shell for the retired company-library file controls.

   Company/organization membership and legacy custody state are not file
   authorization sources under the canonical Permission Matrix. Resource
   sharing is performed through explicit User, Group, or future Guest grants
   on the server-authoritative sharing surfaces.
------------------------------------------------------------------- */

(function () {
    "use strict";

    window.NationsCompanyFiles = window.NationsCompanyFiles || {
        retired: true,
        authority: "explicit_resource_grants"
    };
}());
