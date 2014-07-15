/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var PrintFileInfoDialog = Backbone.View.extend({
	el: '#printer-file-info',
	file_list: null,
	template: _.template( $("#printerfile-info-template").html() ),
	printer_file: null,
	events: {
		'click .actions .remove': 'onDeleteClicked',
		'click .actions .print': 'onPrintClicked',
		'click .actions .download': 'onDownloadClicked'
	},
	initialize: function(params) {
		this.file_list = params.file_list;
	},
	render: function() {
		this.$el.find('.dlg-content').html(this.template({ 
        	p: this.printer_file,
        	time_format: app.utils.timeFormat
        }));
	},
	open: function(printer_file) {
		this.printer_file = printer_file;
		this.render();
		this.$el.foundation('reveal', 'open');
	},
	onDeleteClicked: function() {
		this.file_list.doDelete(this.printer_file.id, this.printer_file.local_filename);
		this.$el.foundation('reveal', 'close');
	},
	onPrintClicked: function() {
		app.printingView.startPrint(this.printer_file.local_filename /*,completion callback*/);
		this.$el.foundation('reveal', 'close');
	},
	onDownloadClicked: function() {
		this.file_list.doDownload(this.printer_file.id);
		this.$el.foundation('reveal', 'close');
	}
});

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

var PrintFilesListView = Backbone.View.extend({
	template: _.template( $("#print-file-list-template").html() ),
	info_dialog: null,
	file_list: null,
	loader: null,
	initialize: function() {
		this.file_list = new PrintFileCollection();
		this.info_dialog = new PrintFileInfoDialog({file_list: this});
		this.loader = this.$el.find('h3 .icon-refresh');
		this.refresh();
	},
	render: function() { 
        this.$el.find('.design-list-container').html(this.template({ 
        	print_files: this.file_list.toJSON(),
        	time_format: app.utils.timeFormat,
        	size_format: app.utils.sizeFormat
        }));
    },
	refresh: function() {
		if (!this.loader.hasClass('animate-spin')) {
			this.loader.addClass('animate-spin');
			var self = this;

			this.file_list.fetch({
				success: function() {
					self.loader.removeClass('animate-spin');
					self.render();
				},
				error: function() {
					noty({text: "There was an error retrieving design list", timeout: 3000});
					self.loader.removeClass('animate-spin');
				}
			});
		}	
	},
	onInfoClicked: function(el) {
		var row = $(el).closest('.row');
		var printfile_id = row.data('printfile-id');
		var print_file = this.file_list.get(printfile_id);

		this.info_dialog.open(print_file.toJSON());
	},
	doDownload: function(id) {
		var self = this;
		var container = this.$el.find('#print-file-'+id);
		var options = container.find('.print-file-options');
		var progress = container.find('.progress');

		options.hide();
		progress.show();

        $.getJSON('/api/cloud-slicer/print-files/'+id+'/download', 
        	function(response) {
        		self.render();
	        }).fail(function(){
	            noty({text: "Couldn't download the print file.", timeout: 3000});
	        }).always(function(){
	            options.show();
				progress.hide();
	        });
	},
	doDelete: function(id, filename) {
		var self = this;

        $.ajax({
            url: '/api/files/local/'+filename,
            type: "DELETE",
            success: function() {            	
            	//Update model
            	var print_file = self.file_list.get(id);

            	if (print_file) {
            		print_file.set('local_filename', null);
            	}

            	self.render();
            	noty({text: filename+" deleted form your AstroBox", type:"success", timeout: 3000});
            },
            error: function() {
            	noty({text: "Error deleting "+filename, timeout: 3000});
            }
        });
	},
	downloadProgress: function(data) {
		var container = this.$el.find('#print-file-'+data.id);
		var progress = container.find('.progress .meter');

		if (data.type == "progress") {
			progress.css('width', data.progress+'%');
		} else if (data.type == "success") {
			var print_file = this.file_list.get(data.id);

			if (print_file) {
				print_file.set('local_filename', data.filename);
				print_file.set('print_time', data.print_time);
				print_file.set('layer_count', data.layer_count);
			}

		} else if (data.type == "success") {
			console.log('done');
		}
	}
});

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadView: null,
	printFilesListView: null,
	events: {
		'click h3 .icon-refresh': 'refreshPrintFiles' 
	},
	initialize: function() {
		this.uploadView = new FileUploadView({el: this.$el.find('.design-file-upload')});
		this.printFilesListView = new PrintFilesListView({el: this.$el.find('.design-list')});
	},
	refreshPrintFiles: function() {
		this.printFilesListView.refresh();
	}
});

function home_info_print_file_clicked(el, evt) 
{
	evt.preventDefault();
	app.homeView.printFilesListView.onInfoClicked.call(app.homeView.printFilesListView, $(el));
}

function home_download_print_file_clicked(id, evt)
{
	evt.preventDefault();
	app.homeView.printFilesListView.doDownload.call(app.homeView.printFilesListView, id);
}

function home_print_print_file_clicked(filename, evt)
{
	evt.preventDefault();
	app.printingView.startPrint(filename);
}