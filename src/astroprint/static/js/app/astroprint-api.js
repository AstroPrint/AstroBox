/*
 *  (c) 2018 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var AstroPrintApi = function(eventManager) {
  eventManager.on('astrobox:userLoggedOut', _.bind(function(){
    this._clearToken();
  },this));
}

AstroPrintApi.prototype = {
  EXPIRATION_BUFFER: 10,
  token: null,

  //API functions

  /*
    To create a new api call simply return a the promise from a call to this._apiRequest as defined below. This function
    takes care of token, token refresh and 401 erros automatically.

    _apiRequest(endpoint, ajaxSettings)

    endpoint: This is the API endpoint, starting with / and without including the api version or host
    ajaxSettings: Any setting that can be passed to the jQuery ajax options (https://api.jquery.com/jQuery.ajax/) EXCEPT 'url' which
    is automatically set based on the previous parameter.
  */

  me: function()
  {
    return this._apiRequest('/accounts/me?plan=true',{method: 'GET'});
  },

  /* =========== QUEUES =========== */

  /*
    Get queue from device
  */
  queue: function()
  {
    return this._apiRequest('/devices/'+ BOX_ID + '/print-queue', {method: 'GET'});
  },

  /*
    Get print files from later list
  */
  later: function()
  {
    return this._apiRequest('/print-queues/print-later', {method: 'GET'});
  },

  /* Update status of queue element
    @elementID: ID of queue element
    @data: Attributes to change
  */
  updateQueueElement: function(elementID, data)
  {
    return this._apiRequest('/print-queues/'+ elementID, {
      method: 'PATCH',
      data: JSON.stringify(data)
    });
  },

  /* Swap positions between two queue elements
    @modelA_ID: ID of queue element A
    @modelB_ID: ID of queue element B
  */
  swapQueueElementsPos: function(modelA_ID, modelB_ID)
  {
    return this._apiRequest('/print-queues/'+ modelA_ID + "/swap-positions" ,  {
      method: 'PATCH',
      data: JSON.stringify({"elementqueue_id": modelB_ID})
    });
  },

  /* Add elemento to the queue
    @elementID: ID of queue element
  */
  addElemenToQueue: function(elementID)
  {
    return this._apiRequest('/print-queues', {
      method: 'POST',
      data: JSON.stringify({"printfile_id" : elementID, "device_id": BOX_ID}),
      contentType: 'application/json; charset=utf-8'
    });
  },

  /* Remove queue element
    @elementID: ID of queue element
  */
  removeQueueElement: function(elementID)
  {
    return this._apiRequest('/print-queues/' + elementID, { method: 'DELETE'});
  },

  /* Remove all queue elements or only those macthing passed status.
    @status: pending || finished
  */
  clearQueue: function(status)
  {
    return this._apiRequest('/devices/' + BOX_ID + '/print-queue', {
      method: 'DELETE',
      data: JSON.stringify( {"status" : status} ),
      contentType: 'multipart/form-data'
    });
  },

  /* =========== PRINTFILES =========== */

  /* Upload a local file to the user's account
    @formData: Form including the File,
    @query: Include project_id,design_id,printer, material...
  */
  uploadPrintfileToCloud: function(formData, query)
  {
    return this._apiRequest('/printfiles/' + query, {
      method: 'POST',
      data: formData,
      processData: false,
      contentType: false
    });
  },


  //Private functions

  _getAccessToken: function()
  {
    if (LOGGED_PUBLIC_KEY) {
      if (this.token) {
        token = this.token;
      } else {
        token = localStorage.getItem('access_token');
        if (token) {
          this.token = JSON.parse(token);
        }
      }

      if (token && token.user_id == LOGGED_PUBLIC_KEY) {
        if (token.expires_at > this._nowInSecs()) {
          return $.Deferred().resolve(token);
        } else {
          //time to refresh
          return this._refreshAccessToken();
        }
      } else {
        return this._getNewAccessToken();
      }
    } else {
      this._clearToken();
      return $.Deferred().reject({
        status: 'no_logged_user',
        statusText: 'No User is logged'
      });
    }
  },

  _getNewAccessToken: function()
  {
    return $.getJSON(API_BASEURL+'astroprint/login-key')
      .then(_.bind(function(data) {
        return $.post({
          url: AP_API_HOST+'/v2/token',
          data: {
            client_id: AP_API_CLIENT_ID,
            grant_type: 'astroprint_login_key',
            scope: 'all',
            login_key: data.login_key
          },
          headers: null
        })
          .then(_.bind(function(token) {
            this._saveToken(token);
            return this.token;
          }, this));
      }, this));
  },

  _refreshAccessToken: function()
  {
    return $.post({
      url: AP_API_HOST+'/v2/token',
      data: {
        client_id: AP_API_CLIENT_ID,
        grant_type: 'refresh_token',
        refresh_token: this.token.refresh_token
      },
      headers: null
    }).then(
      _.bind(function(token){
        this._saveToken(token);
        return this.token;
      }, this),
      _.bind(function(err){
        return this._getNewAccessToken();
      }, this)
    )
  },

  _saveToken: function(token)
  {
    this.token = {
      access_token: token.access_token,
      expires_at: Math.round( this._nowInSecs() + token.expires_in - this.EXPIRATION_BUFFER ),
      refresh_token: token.refresh_token,
      user_id: LOGGED_PUBLIC_KEY
    };

    localStorage.setItem('access_token', JSON.stringify(this.token));
  },

  _apiRequest: function(endpoint, settings)
  {
    return this._getAccessToken()
      .then(function(token) {
        //This header needs setup by default using $.ajaxSetip needs to be removed for AP requests
        delete $.ajaxSettings.headers['X-Api-Key'];

        return $.ajax(_.extend(settings, {
          url: AP_API_HOST + '/v2' + endpoint,
          headers: {
            Authorization: 'Bearer '+ token.access_token
          },
          cache: true,
          beforeSend: function(xhr, settings) {
            //Se need to set the header back for other AstroBox API requests
            $.ajaxSettings.headers['X-Api-Key'] = UI_API_KEY;
          }
        })).then(
          null,
          _.bind(function(err) {
            if (err.status == 401) {
              // This is bad, so we need to remove all tokens
              this._clearToken();
            }

            return err;
          }, this)
        )
    });
  },

  _clearToken: function()
  {
    this.token = null;
    localStorage.removeItem('access_token');
  },

  _nowInSecs: function()
  {
    return Date.now() / 1000;
  }
};
