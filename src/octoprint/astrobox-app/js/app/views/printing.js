/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var PrintingView = Backbone.View.extend({
	el: '#printing-view',
    events: {
        'click button.stop-print': 'stopPrint',
        'click button.pause-print': 'pausePrint'
    },
	startPrint: function(filename, cb) {
        $.ajax({
            url: '/api/files/local/'+filename,
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: "select", print: true})
        }).
        done(function() {
        	//app.showPrinting();
        	cb(true);
        }).
        fail(function() {
        	noty({text: "There was an error starting the print", timeout: 3000});
        	cb(false);
        });
	},
    stopPrint: function() {
        this._jobCommand('cancel');
    },
    pausePrint: function() {
        this._jobCommand('pause');
    },
    _jobCommand: function(command) {
        $.ajax({
            url: API_BASEURL + "job",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: command})
        });
    }
});