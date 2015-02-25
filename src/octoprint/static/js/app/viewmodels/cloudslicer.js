/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

function CloudSlicerViewModel(loginStateViewModel) {
    var self = this;

    self.loginState = loginStateViewModel;

    // initialize list helper
    self.listHelper = new ItemListHelper(
        "couldSlicedFiles",
        {
            "name": function(a, b) {
                // sorts ascending
                if (a["name"].toLocaleLowerCase() < b["name"].toLocaleLowerCase()) return -1;
                if (a["name"].toLocaleLowerCase() > b["name"].toLocaleLowerCase()) return 1;
                return 0;
            }
        },
        {
        },
        "name",
        [],
        [],
        CONFIG_GCODEFILESPERPAGE
    );

    self.setupCloudUploader = function()
    {
        var progress_bar = $("#cloud_slicer_upload_progress");

        $("#cloud_slicer_upload").fileupload({
            add: function(e, data) {
                    var uploadErrors = [];
                    var acceptFileTypes = /(\.|\/)(stl|obj|amf)$/i;
                    if(data.originalFiles[0]['name'].length && !acceptFileTypes.test(data.originalFiles[0]['name'])) {
                        uploadErrors.push('Not an accepted file type');
                    }
                    if(uploadErrors.length > 0) {
                        $.pnotify({title: "Error Uploading", text: "There was an error uploading: " + uploadErrors.join("\n"), type: "error"});
                    } else {
                        data.submit();
                    }
            }
        })
        .bind('fileuploadsubmit', function(e, data) {
            var wgt = $(this);
            if (data.files.length) {
                progress_bar.show();
                progress_bar.children('.bar').css('width', '2%');
                $.getJSON('/ajax/cloud-slicer/upload-data?file='+encodeURIComponent(data.files[0].name), function(response) {
                    if (response.url && response.params) {
                        data.formData = response.params;
                        data.url = response.url;
                        data.redirect = response.redirect;
                        wgt.fileupload('send', data);
                    } else {
                        progress_bar.hide();
                        $.pnotify({title: "Error Uploading", text: "There was an error getting upload parameters.", type: "error"});
                    }
                }).fail(function(xhr){
                    progress_bar.hide();
                    $.pnotify({title: "Error Uploading", text: "There was an error getting upload parameters.", type: "error"});
                });
            }
            return false;
        })
        .bind('fileuploadprogress', function (e, data) {
            var progress = Math.max(parseInt(data.loaded / data.total * 100, 10), 2);
            progress_bar.children('.bar').css('width', progress + '%');
        })
        .bind('fileuploadfail', function(e, data) {
            $.pnotify({title: "Error Uploading", text: "There was an error uploading your file: "+ data.errorThrown, type: "error"});
        })
        .bind('fileuploadalways', function(e, data) {
            setTimeout(function() {
                progress_bar.hide();
                progress_bar.children(".bar").css("width", "0%");
            }, 2000);
        }).
        bind('fileuploaddone', function(e, data) {
            if (data.redirect) {
                window.location.href = data.redirect;
            }
        });
    }

    self.refresh = function() {
    	$("#cloud_slicer_accordion .icon-refresh").addClass('icon-spin');
        self._sendCommand('refresh', null, function(error, response) {
        	if (error) {
        		$.pnotify({title: "Error Refreshing", text: "There was an error contacting the cloud slicer.", type: "error"});
        	} else {
            	design_list = [];

            	for (var i=0; i < response.length; i++) {
            		var design = response[i];
            		if (design.gcodes.length > 0) {
	            		design_list.push( {
	            			"id": design.id,
	            			"name": design.name,
	            			"gcodes": design.gcodes
	            		});
	            	}
            	}
            	self.listHelper.updateItems(design_list);        		
        	}

        	$("#cloud_slicer_accordion .icon-refresh").removeClass('icon-spin');
        });
    }

    self.downloadFile = function(gcode_id, filename) {
    	var progress_bar = $("#cloud_download_progress_"+gcode_id);
    	progress_bar.show();
    	self._sendCommand('download', {gcode_id: gcode_id, filename: filename}, function(error, response) {
    		if (error) {
    			$.pnotify({title: "Download failed", text: "Couldn't download the gcode file.", type: "error"});
    		}
    	});
    }

    self._sendCommand = function(command, data, completedCb) {
    	if (!data) data = {};
    	
    	data['command'] = command;

        $.ajax({
            url: API_BASEURL + "cloud-slicer/command",
            type: "POST",
            dataType: "json",
            data: data,
            success: function(response) {
            	completedCb(false, response);
            },
            error: function(xhr) {
            	completedCb(true, '');
            }
        });        
    }

    this.setupCloudUploader();
}