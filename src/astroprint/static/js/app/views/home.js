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
	initialize: function(params) 
	{
		this.file_list = params.file_list;
	},
	render: function() 
	{
		this.$el.find('.dlg-content').html(this.template({ 
        	p: this.printer_file,
        	time_format: app.utils.timeFormat
        }));
	},
	open: function(printer_file) 
	{
		this.printer_file = printer_file;
		this.render();
		this.$el.foundation('reveal', 'open');
	},
	onDeleteClicked: function(e) 
	{
		e.preventDefault();
		this.file_list.doDelete(this.printer_file.id, this.printer_file.local_filename);
		this.$el.foundation('reveal', 'close');
	},
	onPrintClicked: function(e) 
	{
		e.preventDefault();
		this.file_list.startPrint(this.printer_file.local_filename);
		this.$el.foundation('reveal', 'close');
	},
	onDownloadClicked: function(e) 
	{
		e.preventDefault();
		this.file_list.doDownload(this.printer_file.id);
		this.$el.foundation('reveal', 'close');
	}
});

var UploadView = Backbone.View.extend({
	designUpload: null,
	printUpload: null,
	initialize: function()
	{
		var progressBar = this.$el.find('.upload-progress');
		var buttonContainer = this.$el.find('.upload-buttons');

		this.designUpload = new FileUploadDesign({
			progressBar: progressBar,
			buttonContainer: buttonContainer
		});

		this.printUpload = new FileUploadPrint({
			progressBar: progressBar,
			buttonContainer: buttonContainer
		});
	}
});

var FileUploadBase = Backbone.View.extend({
	events: {
		'fileuploadadd': 'onFileAdded',
		'fileuploadsubmit': 'onFileSubmit',
		'fileuploadprogress': 'onUploadProgress',
		'fileuploadfail': 'onUploadFail',
		'fileuploadalways': 'onUploadAlways',
		'fileuploaddone': 'onUploadDone'	
	},
	progressBar: null,
	acceptFileTypes: null,
	buttonContainer: null,
	initialize: function(options) 
	{
		this.progressBar = options.progressBar;
		this.buttonContainer = options.buttonContainer;
		this.$el.fileupload();
	},
	onFileAdded: function(e, data) 
	{
        var uploadErrors = [];
        var acceptFileTypes = this.acceptFileTypes;
        if(data.originalFiles[0]['name'].length && !acceptFileTypes.test(data.originalFiles[0]['name'])) {
            uploadErrors.push('Not a valid file');
        }
        if(uploadErrors.length > 0) {
        	noty({text: "There was an error uploading: " + uploadErrors.join("<br/>"),  timeout: 3000});
        	return false;
        } else {
        	return true;
        }
	},
	onFileSubmit: function(e, data) 
	{
	    if (data.files.length) {
	    	this.buttonContainer.hide();
	        this.progressBar.show();
	        this._updateProgress(5);

	        if (this.beforeSubmit(e, data)) {
	        	$(e.currentTarget).fileupload('send', data);
	        }
	    }
	    return false;
	},
	onUploadProgress: function(e, data) 
	{
        this._updateProgress(Math.max((data.loaded / data.total * 100) * 0.90, 5));
	},
	onUploadFail: function(e, data) 
	{
		noty({text: "There was an error uploading your file: "+ data.errorThrown, timeout: 3000});
	},
	onUploadAlways: function(e, data) {},
	onUploadDone: function(e, data) {},
	beforeSubmit: function(e, data) { return true; },
	_updateProgress: function(percent, message)
	{
		var intPercent = Math.round(percent);

		this.progressBar.find('.meter').css('width', intPercent+'%');
		if (!message) {
			message = "Uploading ("+intPercent+"%)";
		}
		this.progressBar.find('.progress-message span').text(message);
	}
});

var FileUploadDesign = FileUploadBase.extend({
	el: '.file-upload-button.design .file-upload',
	acceptFileTypes: /(\.|\/)(stl|obj|amf)$/i,
	beforeSubmit: function(e, data) 
	{
	    $.getJSON('/api/astroprint/upload-data?file='+encodeURIComponent(data.files[0].name), _.bind(function(response) {
	        if (response.url && response.params) {
	            data.formData = response.params;
	            data.url = response.url;
	            data.redirect = response.redirect;
	        	$(e.currentTarget).fileupload('send', data);
	        } else {
	            this.progressBar.hide();
				this.buttonContainer.show();

	            noty({text: 'There was an error getting upload parameters.', timeout: 3000});
	        }
	    }, this)).fail(_.bind(function(xhr){
	        this.progressBar.hide();
	        this.buttonContainer.show();
	        noty({text: 'There was an error getting upload parameters.', timeout: 3000});
	    }, this));

	    return false;
	},
	onUploadAlways: function(e, data) 
	{
        setTimeout(_.bind(function() {
            this.progressBar.hide();
           	this.buttonContainer.show();
           	this._updateProgress(0);
        }, this), 2000);
	},
	onUploadDone: function(e, data) 
	{
		this._updateProgress(95, 'Preparing to slice');
        if (data.redirect) {
            window.location.href = data.redirect;
        }
	}
});

var FileUploadPrint = FileUploadBase.extend({
	el: '.file-upload-button.print .file-upload',
	acceptFileTypes: /(\.|\/)(gcode)$/i,
	onUploadDone: function(e, data) 
	{
		var filename = data.files[0].name;
    	this._updateProgress(95, 'Analyzing G-Code');
    	app.eventManager.once('astrobox:MetadataAnalysisFinished', _.bind(function(gcodeData){
    		if (gcodeData.file == filename) {
	    		noty({text: "File uploaded succesfully", type: 'success', timeout: 3000});
	    		app.router.homeView.refreshPrintFiles(true);
		        this.progressBar.hide();
		        this.buttonContainer.show();
		        this._updateProgress(0);
		    }
    	}, this));
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
		app.eventManager.on('astrobox:cloudDownloadEvent', this.downloadProgress, this);
		this.refresh(false);
	},
	render: function() 
	{ 
        this.$el.find('.design-list-container').html(this.template({ 
        	print_files: this.file_list.toJSON(),
        	time_format: app.utils.timeFormat,
        	size_format: app.utils.sizeFormat
        }));
    },
	refresh: function(syncCloud) 
	{
		if (!this.loader.hasClass('animate-spin')) {
			this.loader.addClass('animate-spin');

			var success = _.bind(function() {
				this.loader.removeClass('animate-spin');
				this.render();
			}, this);

			var error = _.bind(function() {
				noty({text: "There was an error retrieving design list", timeout: 3000});
				this.loader.removeClass('animate-spin');
			}, this);

			if (syncCloud) {
				this.file_list.syncCloud({success: success, error: error});
			} else {
				this.file_list.fetch({success: success, error: error});
			}
		}	
	},
	onInfoClicked: function(el) 
	{
		var row = $(el).closest('.row');
		var printfile_id = row.data('printfile-id');
		var print_file = this.file_list.get(printfile_id);

		if (print_file) {
			this.info_dialog.open(print_file.toJSON());
		} else {
			console.error('Invalid printfile_id: '+printfile_id);
		}
	},
	startPrint: function(filename, cb) 
	{
        $.ajax({
            url: '/api/files/local/'+filename,
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: "select", print: true})
        }).
        done(_.bind(function() {
            this.$el.find('.progress .filename').text(filename);
            if (cb) {
        	   cb(true);
            }
        }, this)).
        fail(function() {
        	noty({text: "There was an error starting the print", timeout: 3000});
            if (cb) {
        	   cb(false);
            }
        });
	},
	doDownload: function(id) 
	{
		var self = this;
		var container = this.$el.find('#print-file-'+id);
		var options = container.find('.print-file-options');
		var progress = container.find('.progress');

		options.hide();
		progress.show();

        $.getJSON('/api/astroprint/print-files/'+id+'/download', 
        	function(response) {
        		self.render();
	        }).fail(function(){
	            noty({text: "Couldn't download the print file.", timeout: 3000});
	        }).always(function(){
	            options.show();
				progress.hide();
	        });
	},
	doDelete: function(id, filename) 
	{
		var self = this;

        $.ajax({
            url: '/api/files/local/'+filename,
            type: "DELETE",
            success: function() {            	
            	//Update model
            	var print_file = self.file_list.get(id);

            	if (print_file) {
            		if (print_file.get('local_only')) {
            			self.file_list.remove(print_file);
            		} else {
            			print_file.set('local_filename', false);
            		}
            	}

            	self.render();
            	noty({text: filename+" deleted form your "+PRODUCT_NAME, type:"success", timeout: 3000});
            },
            error: function() {
            	noty({text: "Error deleting "+filename, timeout: 3000});
            }
        });
	},
	downloadProgress: function(data) 
	{
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
	initialize: function() 
	{
		this.uploadView = new UploadView({el: this.$el.find('.file-upload-view')});
		this.printFilesListView = new PrintFilesListView({el: this.$el.find('.design-list')});
	},
	refreshPrintFiles: function() 
	{
		this.printFilesListView.refresh(true);
	}
});

function home_info_print_file_clicked(el, evt) 
{
	evt.preventDefault();
	app.router.homeView.printFilesListView.onInfoClicked.call(app.router.homeView.printFilesListView, $(el));
}

function home_download_print_file_clicked(id, evt)
{
	evt.preventDefault();
	app.router.homeView.printFilesListView.doDownload.call(app.router.homeView.printFilesListView, id);
}

function home_print_print_file_clicked(filename, evt)
{
	evt.preventDefault();
	app.router.homeView.printFilesListView.startPrint(filename);
}