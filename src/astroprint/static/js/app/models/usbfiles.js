/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var USBFile = Backbone.Model.extend({
  defaults: {
    'name': '',
    'location': '',
    'image': null
  }
});

var USBFileCollection = Backbone.Collection.extend({
  model: USBFile,
  url: API_BASEURL + "files/folder-contents",
  extensionsAllowed: ['.gcode'],
  localStorages: [],
  initialize: function(){
    console.log('asldkfj;alskdjf')
    $.getJSON('/api/files/file-browsing-extensions')
      .done(function(data){
        this.extensionsAllowed = data;
      })
      .fail(function(error){
        console.error(error);
      });

    $.getJSON('/api/files/removable-drives')
      .done(_.bind(function(data){
        this.localStorages = data;
      },this))
      .fail(function(error){
        console.error(error);
      });
  },
  extensionMatched: function(file)
  {
    var matched = false;

    for(var i=0; !matched && i<this.extensionsAllowed.length; i++){
      matched = file.endsWith(this.extensionsAllowed[i]);
    }

    return matched;
  },
  topLocationMatched: function(location)
  {
    var matched = false;

    for(var i=0; !matched && i<this.localStorages.length; i++){
      matched = (location == (this.localStorages[i].name));
    }

    return matched;
  },
  syncLocation: function(location)
  {
    return this.fetch({
      data: {
        location: location ? location : '/'
      }
    });
  }
});
