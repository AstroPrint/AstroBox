/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var USBFile = Backbone.Model.extend({
  defaults: {
    'name': '',
    'location': '',
    'image': null,
    'size': null
  }
});

var USBFileCollection = Backbone.Collection.extend({
  model: USBFile,
  url: API_BASEURL + "files/folder-contents",
  extensionsAllowed: ['gcode'],
  localStorages: [],
  initialize: function(){
    this.refreshExtensions();

    $.getJSON('/api/files/removable-drives')
      .done(_.bind(function(data){
        this.localStorages = data;
      },this))
      .fail(function(error){
        console.error(error);
      });
  },
  onDriveAdded: function(path)
  {
    this.localStorages.push(path);
  },
  onDriveRemoved: function(path)
  {
    var idx = this.localStorages.indexOf(path)
    if (idx >= 0) {
      delete this.localStorages[idx];
    }
  },
  isMounted: function(path)
  {
    return this.localStorages.indexOf(path) >= 0;
  },
  refreshExtensions: function()
  {
    return $.getJSON('/api/files/file-browsing-extensions')
      .done(_.bind(function(data){
        this.extensionsAllowed = data;
      }, this))
      .fail(function(error){
        console.error(error);
      });
  },
  extensionMatched: function(file)
  {
    return _.find(this.extensionsAllowed, function(ext) { return file.toLowerCase().endsWith('.' + ext) } ) != undefined;
  },
  topLocationMatched: function(location)
  {
    return this.localStorages.indexOf(location) >= 0;
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
