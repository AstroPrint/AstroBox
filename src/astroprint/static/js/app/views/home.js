/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var PrintFileInfoDialog = Backbone.View.extend({
	el: '#print-file-info',
	file_list_view: null,
	template: _.template( $("#printfile-info-template").html() ),
	print_file_view: null,
	events: {
		'click .actions a.remove': 'onDeleteClicked',
		'click .actions a.print': 'onPrintClicked',
		'click .actions a.download': 'onDownloadClicked'
	},
	initialize: function(params) 
	{
		this.file_list_view = params.file_list_view;
	},
	render: function() 
	{
		this.$el.find('.dlg-content').html(this.template({ 
        	p: this.print_file_view.print_file.toJSON(),
        	time_format: app.utils.timeFormat
        }));
	},
	open: function(print_file_view) 
	{
		this.print_file_view = print_file_view;
		this.render();
		this.$el.foundation('reveal', 'open');
	},
	onDeleteClicked: function(e) 
	{
		e.preventDefault();

		var print_file = this.print_file_view.print_file;

		if (print_file) {
			var filename = print_file.get('local_filename');
			var id = print_file.get('id');
			var loadingBtn = $(e.currentTarget).closest('.loading-button');

			loadingBtn.addClass('loading');
	        $.ajax({
	            url: '/api/files/local/'+filename,
	            type: "DELETE",
	            success: _.bind(function() {
	            	//Update model 
            		if (print_file.get('local_only')) {
            			this.file_list_view.file_list.remove(print_file);
            		} else {
            			print_file.set('local_filename', false);
            		}

	            	noty({text: filename+" deleted form your "+PRODUCT_NAME, type:"success", timeout: 3000});
	            	this.print_file_view.render();
	            	this.$el.foundation('reveal', 'close');
	            }, this),
	            error: function() {
	            	noty({text: "Error deleting "+filename, timeout: 3000});
	            },
	            always: function() {
					loadingBtn.removeClass('loading');
	            }
	        });
	    }
	},
	onPrintClicked: function(e) 
	{
		this.print_file_view.printClicked(e);
		this.$el.foundation('reveal', 'close');
	},
	onDownloadClicked: function(e) 
	{
		this.print_file_view.downloadClicked(e);
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
		noty({text: "File uploaded succesfully", type: 'success', timeout: 3000});
		app.router.homeView.refreshPrintFiles(true);
		app.router.homeView.printFilesListView.storage_control_view.selectStorage('local');
        this.progressBar.hide();
        this.buttonContainer.show();
        this._updateProgress(0);
	}
});

var PrintFileView = Backbone.View.extend({
	template: _.template( $("#print-file-template").html() ),
	print_file: null,
	list: null,
	printWhenDownloaded: false,
	initialize: function(options)
	{
		this.list = options.list;
		this.print_file = options.print_file;
	},
	render: function()
	{
		var print_file = this.print_file.toJSON();

		if (print_file.local_filename) {
			this.$el.removeClass('remote');
		} else {
			this.$el.addClass('remote');
		}

		this.$el.empty();
		this.$el.html(this.template({
        	p: print_file,
        	time_format: app.utils.timeFormat,
        	size_format: app.utils.sizeFormat			
		}));
		this.delegateEvents({
			'click .left-section, .middle-section': 'infoClicked',
			'click a.print': 'printClicked',
			'click a.download': 'downloadClicked'
		});
	},
	infoClicked: function(evt) 
	{
		if (evt) evt.preventDefault();

		this.list.info_dialog.open(this);
	},
	downloadClicked: function(evt)
	{
		if (evt) evt.preventDefault();

		var options = this.$('.print-file-options');
		var progress = this.$('.progress');

		options.hide();
		progress.show();

        $.getJSON('/api/astroprint/print-files/'+this.print_file.get('id')+'/download')
	        .fail(function(){
	            noty({text: "Couldn't download the print file.", timeout: 3000});
	        })
	        .always(function(){
	            options.show();
				progress.hide();
	        });
	},
	printClicked: function (evt)
	{
		if (evt) evt.preventDefault();

		var filename = this.print_file.get('local_filename');

		if (filename) {
			//We can't use evt because this can come from another source than the row print button
			var loadingBtn = this.$('.loading-button.print');

			loadingBtn.addClass('loading');
	        $.ajax({
	            url: '/api/files/local/'+filename,
	            type: "POST",
	            dataType: "json",
	            contentType: "application/json; charset=UTF-8",
	            data: JSON.stringify({command: "select", print: true})
	        })
	        .done(_.bind(function() {
	        	setTimeout(function(){
	        		loadingBtn.removeClass('loading');
	        	},2000);
	        }, this))
	        .fail(function(xhr) {
	        	var error = null;
	        	if (xhr.status == 409) {
	        		error = xhr.responseText;
	        	}
	        	noty({text: error ? error : "There was an error starting the print", timeout: 3000});
	        	loadingBtn.removeClass('loading');
	        })
	    } else {
	    	//We need to download and print
	    	this.printWhenDownloaded = true;
	    	this.downloadClicked();
	    }
	}
});

var StorageControlView = Backbone.View.extend({
	print_file_view: null,
	events: {
		'click a.local': 'localClicked',
		'click a.cloud': 'cloudClicked'
	},
	selected: null,
	initialize: function(options)
	{
		this.print_file_view = options.print_file_view;
	},
	selectStorage: function(storage)
	{
		this.$('a.active').removeClass('active');
		this.$('a.'+storage).addClass('active');
		this.selected = storage;
		this.print_file_view.render();
	},
	localClicked: function(e)
	{
		e.preventDefault();
		this.selectStorage('local');
	},
	cloudClicked: function(e)
	{
		e.preventDefault();

		if (LOGGED_USER) {
			this.selectStorage('cloud');
	    } else {
	    	$('#login-modal').foundation('reveal', 'open');
	    }
	}
});

var PrintFilesListView = Backbone.View.extend({
	info_dialog: null,
	print_file_views: [],
	storage_control_view: null,
	file_list: null,
	refresh_threshold: 1000, //don't allow refreshes faster than this (in ms)
	last_refresh: 0,
	events: {
		'click .list-header button.sync': 'forceSync' 
	},
	initialize: function(options) {
		this.file_list = new PrintFileCollection();
		this.info_dialog = new PrintFileInfoDialog({file_list_view: this});
		this.storage_control_view = new StorageControlView({
			el: this.$('.list-header ul.storage'),
			print_file_view: this
		});

		app.eventManager.on('astrobox:cloudDownloadEvent', this.downloadProgress, this);
		app.eventManager.on('astrobox:MetadataAnalysisFinished', _.bind(this.onMetadataAnalysisFinished, this));
		this.listenTo(this.file_list, 'remove', this.onFileRemoved);

		this.refresh(options.forceSync, options.syncCompleted);
	},
	render: function() 
	{ 
		var list = this.$('.design-list-container');
		var selectedStorage = this.storage_control_view.selected;

		list.children().detach();

		if (selectedStorage) {
			var filteredViews = _.filter(this.print_file_views, function(p){
				if (selectedStorage == 'local') {
					if (p.print_file.get('local_filename')) {
						return true
					}
				} else if (!p.print_file.get('local_only')) {
					return true;
				}

				return false;
			});
		} else {
			var filteredViews = this.print_file_views;
		}

		if (filteredViews.length) {

			_.each(filteredViews, function(p) {
				list.append(p.$el);
			});
	    } else {
	    	list.html(
		    	'<div class="empty panel radius" align="center">'+
				'	<i class="icon-inbox empty-icon"></i>'+
				'	<h3>Nothing here yet.</h3>'+
				'</div>'
			);
	    }
    },
	refresh: function(syncCloud, doneCb) 
	{
		var now = new Date().getTime();

		if (this.last_refresh < (now - this.refresh_threshold) ) {
			this.last_refresh = now;
			var loadingBtn = this.$('.loading-button.sync');

			if (!loadingBtn.hasClass('loading')) {
				loadingBtn.addClass('loading');

				var success = _.bind(function() {
					this.print_file_views = [];
					this.file_list.each(_.bind(function(print_file, idx) {
						var print_file_view = new PrintFileView({
							list: this,
							print_file: print_file,
							attributes: {'class': 'row'+(idx % 2 ? ' dark' : '')}
						});
						print_file_view.render();
						this.print_file_views.push( print_file_view );
					}, this));

					this.$('.design-list-container').empty();
					this.render();
					loadingBtn.removeClass('loading');

					if (_.isFunction(doneCb)) {
						doneCb(true);
					}

				}, this);

				var error = function() {
					noty({text: "There was an error retrieving design list", timeout: 3000});
					loadingBtn.removeClass('loading');

					if (_.isFunction(doneCb)) {
						doneCb(false);
					}
				};

				if (syncCloud) {
					this.file_list.syncCloud({success: success, error: error});
				} else {
					this.file_list.fetch({success: success, error: error});
				}
			}
		}
	},
	downloadProgress: function(data) 
	{
		var print_file_view = _.find(this.print_file_views, function(v) {
			return v.print_file.get('id') == data.id;
		});
		var progress = print_file_view.$('.progress .meter');
		var label = print_file_view.$('.progress label span');

		if (data.type == "progress") {
			progress.css('width', data.progress+'%');
			label.text(Math.floor(data.progress));
		} else if (data.type == "success") {
			var print_file = print_file_view.print_file;

			if (print_file) {
				print_file.set('local_filename', data.filename);
				print_file.set('print_time', data.print_time);
				print_file.set('layer_count', data.layer_count);

				print_file_view.render();

				if (print_file_view.printWhenDownloaded) {
					print_file_view.printWhenDownloaded = false;
					print_file_view.printClicked();
				}
			}
		} 
	},
	forceSync: function()
	{
		this.refresh(true);
	},
	onFileRemoved: function(print_file)
	{
		//Find the view that correspond to this print file
		var view = _.find(this.print_file_views, function(v) {
			return v.print_file == print_file;
		});

		if (view) {
			//Remove from DOM
			view.remove();

			//Remove from views array
			this.print_file_views.splice(this.print_file_views.indexOf(view), 1);
		}
	},
	onMetadataAnalysisFinished: function(data)
	{
		var affected_view = _.find(this.print_file_views, function(v){
			return v.print_file.get('name') == data.file;
		});

		if (affected_view) {
			affected_view.print_file.set('info', data.result);
			affected_view.render();
		}
	}
});

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadView: null,
	printFilesListView: null,
	events: {
		'show': 'onShow'
	},
	initialize: function(options) 
	{
		this.uploadView = new UploadView({el: this.$el.find('.file-upload-view')});
		this.printFilesListView = new PrintFilesListView({
			el: this.$el.find('.design-list'),
			forceSync: options.forceSync,
			syncCompleted: options.syncCompleted
		});
	},
	refreshPrintFiles: function() 
	{
		this.printFilesListView.refresh(true);
	},
	fileInfo: function(fileId)
	{
		var view = _.find(this.printFilesListView.print_file_views, function(v) {
			return v.print_file.get('id') == fileId;
		})

		if (view) {
			this.printFilesListView.storage_control_view.selectStorage('cloud');
			view.infoClicked();
		}
	},
	onShow: function()
	{
		this.printFilesListView.refresh(false);
	}
});