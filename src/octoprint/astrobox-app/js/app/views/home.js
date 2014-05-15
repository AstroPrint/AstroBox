/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var FileUploadView = Backbone.View.extend({
	events: {
		'fileuploadadd .file-upload': 'onFileAdded',
		'fileuploadsubmit .file-upload': 'onFileSubmit',
		'fileuploadprogress .file-upload': 'onUploadProgress',
		'fileuploadfail .file-upload': 'onUploadFail',
		'fileuploadalways .file-upload': 'onUploadAlways',
		'fileuploaddone .file-upload': 'onUploadDone'	
	},
	progressBar: null,
	button: null,
	uploadWgt: null,
	initialize: function() {
		this.progressBar = this.$el.find('.file-upload-progress');
		this.button = this.$el.find('.file-upload-button');
       	this.uploadWgt = this.$el.find('.file-upload').fileupload();
	},
	onFileAdded: function(e, data) {
        var uploadErrors = [];
        var acceptFileTypes = /(\.|\/)(stl|obj|amf)$/i;
        if(data.originalFiles[0]['name'].length && !acceptFileTypes.test(data.originalFiles[0]['name'])) {
            uploadErrors.push('Not a valid design file');
        }
        if(uploadErrors.length > 0) {
        	noty({text: "There was an error uploading: " + uploadErrors.join("<br/>")});
        	return false;
        } else {
        	return true;
        }
	},
	onFileSubmit: function(e, data) {
	    if (data.files.length) {
	    	var self = this;

	    	this.button.hide();
	        this.progressBar.show();
	        this.progressBar.children('.meter').css('width', '2%');

	        $.getJSON('/api/cloud-slicer/upload-data?file='+encodeURIComponent(data.files[0].name), function(response) {
	            if (response.url && response.params) {
	                data.formData = response.params;
	                data.url = response.url;
	                data.redirect = response.redirect;
	                $(e.currentTarget).fileupload('send', data);
	            } else {
	                self.progressBar.hide();
					this.button.show();

	                noty({text: 'There was an error getting upload parameters.', timeout: 3000});
	            }
	        }).fail(function(xhr){
	            self.progressBar.hide();
	            this.button.show();
	            noty({text: 'There was an error getting upload parameters.', timeout: 3000});
	        });
	    }
	    return false;
	},
	onUploadProgress: function(e, data) {
        var progress = Math.max(parseInt(data.loaded / data.total * 100, 10), 2);
        this.progressBar.children('.meter').css('width', progress + '%');
	},
	onUploadFail: function(e, data) {
		noty({text: "There was an error uploading your file: "+ data.errorThrown, timeout: 3000});
	},
	onUploadAlways: function(e, data) {
		var self = this;

        setTimeout(function() {
            self.progressBar.hide();
            this.button.show();
            self.progressBar.children(".meter").css("width", "0%");
        }, 2000);
	},
	onUploadDone: function(e, data) {
        if (data.redirect) {
            window.location.href = data.redirect;
        }
	}
});

var DesignsView = Backbone.View.extend({
	template: _.template( $("#design-list-template").html() ),
	designs: new DesignCollection(),
	loader: null,
	initialize: function() {
		this.loader = this.$el.find('h3 .icon-spin1');
		this.refresh();
	},
	render: function() { 
        this.$el.find('.design-list-container').html( this.template({ designs: this.designs }) );
    },
	refresh: function() {
		this.loader.show();
		var self = this;

		this.designs.fetch({
			success: function() {
				self.loader.hide();
				self.render();
			},
			error: function() {
				noty({text: "There was an error retrieving design list", timeout: 3000});
				self.loader.hide();
			}
		});		
	},
	onGcodeClicked: function(el) {
		var self = this;
		var container = el.closest('tr');
		var options = container.find('.gcode-options');
		var progress = container.find('.progress');

		options.hide();
		progress.show();

        $.getJSON('/api/cloud-slicer/designs/download/'+el.attr('data-id'), 
        	function(response) {
        		self.render();
	        }).fail(function(){
	            noty({text: "Couldn't download the gcode file.", timeout: 3000});
	        }).done(function(){
	            options.show();
				progress.hide();
	        });
	}
});

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadView: null,
	designsView: null,
	initialize: function() {
		this.uploadView = new FileUploadView({el: this.$el.find('.design-file-upload')});
		this.designsView = new DesignsView({el: this.$el.find('.design-list')});
	}
});

function home_download_gcode_clicked(el)
{
	app.homeView.designsView.onGcodeClicked.call(app.homeView.designsView, $(el));
}