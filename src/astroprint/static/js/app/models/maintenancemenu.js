/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* exported MaintenanceMenuCollection */

 var MaintenanceMenu = Backbone.Model.extend({

 });

 var MaintenanceMenuCollection = Backbone.Collection.extend({
  model: MaintenanceMenu,
  url: API_BASEURL + "maintenance-menu",
  comparator: function(item) {
    return item.get('type');
  }
});
