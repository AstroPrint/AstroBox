var CameraView = Backbone.View.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  serverUrl: null,
  localSessionId: null,
  events: {
	'click .buttons .columns .success': 'startStreaming',
	'click .buttons .columns .secondary': 'stopStreaming'
  },
  initialize: function(options)
  {
	this.serverUrl = "http://" + window.location.hostname + ":8088/janus";
	startStreaming = this.startStreaming;
	this.initJanus();

	// Initialize the library (all console debuggers enabled)
	Janus.init({debug: "all", callback: function() {
		console.log('Janus Initialized')
	}});

	this.render();
  },
  render: function() {
	this.$el.html(this.template());
  },
  initJanus: function(){
	this.sessionId = null;
  },
  startStreaming: function(e){
	$.when( 
		$.getJSON(API_BASEURL + 'settings/camera/streaming'),
		$.ajax({
			url: API_BASEURL + "camera/init-janus",
			type: "POST",
			dataType: "json",
			contentType: "application/json; charset=UTF-8",
			data: ''
		})
	)
		.done(_.bind(function(settings, session){
			this.localSessionId = session.sessionId;

			if(!this.$('#remotevideo').is(':visible')) {
				this.$('.video-container .columns').hide();
				this.$('#remotevideo').show();
					
				if(!Janus.isWebrtcSupported()) {
					noty({text: "WebRTC is not supported in this browser... ", timeout: 3000});
					return;
				}

				// Create session
				var janus = new Janus({
					server: this.serverUrl,
					apisecret: 'd5faa25fe8e3438d826efb1cd3369a50',
					success: _.bind(function() {

						var streamingPlugIn = null;
						var selectedStream = settings.encoding == 'h264' ? 1 : 2;
						var sizeVideo = settings.size;

						// Attach to streaming plugin
						janus.attach({
							plugin: "janus.plugin.streaming",
							success: function(pluginHandle) {
								streamingPlugIn = pluginHandle;

								var body = { "request": "watch", id: selectedStream };
								streamingPlugIn.send({"message": body});
							},
							error: function(error) {
								console.error(error);
								noty({text: "Error communicating with the WebRTC system.", timeout: 3000});
							},
							onmessage: _.bind(function(msg, jsep) {
								console.log(" ::: Got a message :::");
								console.log(JSON.stringify(msg));
								var result = msg["result"];
								if(result !== null && result !== undefined) {
									if(result["status"] !== undefined && result["status"] !== null) {
										var status = result["status"];
										if(status === 'stopped')
											this.stopStreaming();
									}
								} else if(msg["error"] !== undefined && msg["error"] !== null) {
									console.error(msg["error"]);
									noty({text: "Unable to communicate with the camera.", timeout: 3000});
									this.stopStreaming();
									return;
								}
								if(jsep !== undefined && jsep !== null) {
									console.log("Handling SDP as well...");
									console.log(jsep);
									// Answer
									streamingPlugIn.createAnswer(
										{
											jsep: jsep,
											media: { audioSend: false, videoSend: false },	// We want recvonly audio/video
											success: function(jsep) {
												console.log("Got SDP!");
												console.log(jsep);
												var body = { "request": "start" };
												streamingPlugIn.send({"message": body, "jsep": jsep});
											},
											error: function(error) {
												console.warn("WebRTC error... " + JSON.stringify(error));
											}
										});
								}
							}, this),
							onremotestream: function(stream) {
								console.log(" ::: Got a remote stream :::");
								console.log(JSON.stringify(stream));
								$("#remotevideo").bind("playing", function () {

								});
								attachMediaStream($('#remotevideo').get(0), stream);
							},
							oncleanup: function() {
								Janus.log(" ::: Got a cleanup notification :::");
							}
						});
					}, this),
					error: function(error) {
						console.error(error);
						noty({text: "Unable to start the WebRTC session.", timeout: 3000});
						//This is a fatal error. The application can't recover. We should probably show an error state in the app.
					},
					destroyed: _.bind(this.initJanus, this)
				});
		      }
		},this))
		.fail(_.bind(function(error){
			console.error(error);
			noty({text: "Unable to start the WebRTC system.", timeout: 3000});
			this.initJanus();
		}, this));
  },
  stopStreaming: function(e){
	  console.log('stopStreaming');
	  if (this.sessionId) {
		  this.$('#remotevideo').hide();
		  this.$('.video-container .columns').show();
		  $.ajax({
			url: API_BASEURL + "camera/stop-janus",
			type: "POST",
			dataType: "json",
			contentType: "application/json; charset=UTF-8",
			data: {
				sessionId: this.localSessionId
			}
		  })
		  	.always(_.bind(this.initJanus, this))
      }	
  }
});