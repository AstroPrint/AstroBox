/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var PrintFileInfoDialog = Backbone.View.extend({
	el: '#printer-file-info',
	template: _.template( $("#printerfile-info-template").html() ),
	printer_file: null,
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
	doDelete: function() {

	},
	doPrint: function() {

	},
	doDownload: function() {

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

var DesignsView = Backbone.View.extend({
	template: _.template( $("#design-list-template").html() ),
	info_dialog: null,
	designs: null,
	loader: null,
	initialize: function() {
		this.designs = new DesignCollection();
		this.info_dialog = new PrintFileInfoDialog();
		this.loader = this.$el.find('h3 .icon-refresh');
		this.refresh();
	},
	render: function() { 
		var print_files = [];
		this.designs.each(function(d) {
			print_files_design = d.get('print_files');
			_.each(print_files_design, function(p) {
				p.design_id = d.get('id');
				p.thumb = d.get('images').thumbnail;
				p.image = d.get('images').square;
			});
			print_files = print_files.concat(print_files_design);
		});
        this.$el.find('.design-list-container').html(this.template({ 
        	print_files: print_files,
        	time_format: app.utils.timeFormat,
        	size_format: app.utils.sizeFormat
        }));
    },
	refresh: function() {
		if (!this.loader.hasClass('animate-spin')) {
			this.loader.addClass('animate-spin');
			var self = this;

			this.designs.fetch({
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
		var design_id = row.data('design-id');
		var printfile_id = row.data('printfile-id');

		var design = this.designs.get(design_id);
		var print_files = design.get('print_files');

		var print_file = _.find(print_files, function(p) {
			return p.id == printfile_id;
		});

		this.info_dialog.open(print_file);
	},
	onDownloadClicked: function(el) {
		var self = this;
		var container = el.closest('.row');
		var options = container.find('.print-file-options');
		var progress = container.find('.progress');

		options.hide();
		progress.show();

        $.getJSON('/api/cloud-slicer/designs/'+container.data('design-id')+'/print-files/'+el.data('id')+'/download', 
        	function(response) {
        		self.render();
	        }).fail(function(){
	            noty({text: "Couldn't download the gcode file.", timeout: 3000});
	        }).always(function(){
	            options.show();
				progress.hide();
	        });
	},
	onDeleteClicked: function(el) {
		var filename = el.data('local-name');
		var self = this;

        $.ajax({
            url: '/api/files/local/'+filename,
            type: "DELETE",
            success: function() {            	
            	//Update model
            	var print_file = self.designs.find_print_file(
            		self.designs.get(self.$el.find('#print-file-'+el.data('id')).data('design-id')), 
            		el.data('id')
            	);

            	if (print_file) {
            		print_file.local_filename = null
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
			var print_file = this.designs.find_print_file(container.data('design-id'), data.id)

			if (print_file) {
				print_file.local_filename = data.filename;
				print_file.print_time = data.print_time;
				print_file.layer_count = data.layer_count
			}

		} else if (data.type == "success") {
			console.log('done');
		}
	}
});

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadView: null,
	designsView: null,
	events: {
		'click h3 .icon-refresh': 'refreshDesigns' 
	},
	initialize: function() {
		this.uploadView = new FileUploadView({el: this.$el.find('.design-file-upload')});
		this.designsView = new DesignsView({el: this.$el.find('.design-list')});
	},
	refreshDesigns: function() {
		this.designsView.refresh();
	}
});

function home_info_print_file_clicked(el, evt) 
{
	evt.preventDefault();
	app.homeView.designsView.onInfoClicked.call(app.homeView.designsView, $(el));
}

function home_download_print_file_clicked(el, evt)
{
	evt.preventDefault();
	app.homeView.designsView.onDownloadClicked.call(app.homeView.designsView, $(el));
}

function home_delete_print_file_clicked(el, evt)
{
	evt.preventDefault();
	app.homeView.designsView.onDeleteClicked.call(app.homeView.designsView, $(el));
}

function home_print_print_file_clicked(el, evt)
{
	evt.preventDefault();
	var $el = $(el);

	$el.addClass('loading');
	app.printingView.startPrint($el.data('filename'), function() {
		$el.removeClass('loading');
	});
}