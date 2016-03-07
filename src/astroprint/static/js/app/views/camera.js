var CameraView = Backbone.View.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  events: {
		'click .buttons .columns .success': 'startStreaming',
		'click .buttons .columns .secondary': 'stopStreaming'
  },
  janus: null,
  settings: null,
  started: null,
  server: null,
  localSessionId: null,
  initJanus: function(){
	  janus = null;
	  streaming = null;
	  this.started = false;
	  spinner = null;  
  },
  initialize: function(options)
  {
	  this.server = "http://" + window.location.hostname + ":8088/janus";
	  startStreaming = this.startStreaming;
	  this.initJanus();
	  
	  // Initialize the library (all console debuggers enabled)
	  Janus.init({debug: "all", callback: function() {
		console.log('Janus Initialized')
	  }});
	  
	  if (!this.settings) {
			$.getJSON(API_BASEURL + 'settings/camera/streaming', null, _.bind(function(data) {
				this.settings = data;
				this.render();
			}, this))
			.fail(function() {
				noty({text: "There was an error getting Camera settings.", timeout: 3000});
			});
		} else {
			this.render();
		}
  },
  render: function() {
	  	this.$el.html(this.template({ 
			settings: this.settings
		}));
	
		this.$el.foundation();
	
		this.delegateEvents(this.events);
		
		this.$el.removeClass('hide');
  },
  startStreaming: function(e){
	  
	  $.ajax({
		  url: API_BASEURL + "camera/startStreaming",
		  type: "POST",
		  dataType: "json",
		  contentType: "application/json; charset=UTF-8",
		  data: '',
		  success: _.bind(function(r){
			  this.localSessionId = r.sessionId;
			  console.log('startStreaming');
			  if(!this.$('#remotevideo').is(':visible')){
				  this.$('.video-container .columns').hide();
				  this.$('#remotevideo').show();
				  

				  if(this.started)
						return;
					this.started = true;
					
					if(!Janus.isWebrtcSupported()) {
						console.log("No WebRTC support... ");
						return;
					}
					// Create session
					janus = new Janus(
					{
						server: this.server,
						apisecret: 'd5faa25fe8e3438d826efb1cd3369a50',
						success: function() {
							// Attach to streaming plugin
							janus.attach(
								{
									plugin: "janus.plugin.streaming",
									success: function(pluginHandle) {
										streaming = pluginHandle;
										
										selectedStream=1;
										Janus.log("Selected video id #" + selectedStream);
										if(selectedStream === undefined || selectedStream === null) {
											bootbox.alert("Select a stream from the list");
											return;
										}
										$('#streamset').attr('disabled', true);
										$('#streamslist').attr('disabled', true);
										$('#watch').attr('disabled', true).unbind('click');
										var body = { "request": "watch", id: parseInt(selectedStream) };
										streaming.send({"message": body});
										// No remote video yet
										if(spinner == null) {
											var target = document.getElementById('stream');
											spinner = new Spinner({top:100}).spin(target);
										} else {
											spinner.spin();
										}
									},
									error: function(error) {
										Janus.error("  -- Error attaching plugin... ", error);
										console.log("Error attaching plugin... " + error);
									},
									onmessage: function(msg, jsep) {
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
											console.log(msg["error"]);
											this.stopStreaming();
											return;
										}
										if(jsep !== undefined && jsep !== null) {
											console.log("Handling SDP as well...");
											console.log(jsep);
											// Answer
											streaming.createAnswer(
												{
													jsep: jsep,
													media: { audioSend: false, videoSend: false },	// We want recvonly audio/video
													success: function(jsep) {
														console.log("Got SDP!");
														console.log(jsep);
														var body = { "request": "start" };
														streaming.send({"message": body, "jsep": jsep});
													},
													error: function(error) {
														//Janus.error("WebRTC error:", error);
														console.log("WebRTC error... " + JSON.stringify(error));
													}
												});
										}
									},
									onremotestream: function(stream) {
										console.log(" ::: Got a remote stream :::");
										console.log(JSON.stringify(stream));
										$("#remotevideo").bind("playing", function () {
											if(spinner !== null && spinner !== undefined)
												spinner.stop();
											spinner = null;
										});
										attachMediaStream($('#remotevideo').get(0), stream);
									},
									oncleanup: function() {
										Janus.log(" ::: Got a cleanup notification :::");
									}
								});
						},
						error: function(error) {
							//Janus.error(error);
							console.log(error, function() {
								window.location.reload();
							});
						},
						destroyed: function() {
							window.location.reload();
						}
					});
		      }
		  },this),
		  error: this.initJanus()
	  });
  },
  stopStreaming: function(e){
	  console.log('stopStreaming');
	  if(this.$('#remotevideo').is(':visible')){
		  this.$('#remotevideo').hide();
		  this.$('.video-container .columns').show();
		  $.ajax({
			  url: API_BASEURL + "camera/stopStreaming",
			  type: "POST",
			  dataType: "json",
			  contentType: "application/json; charset=UTF-8",
			  data: JSON.stringify(this.localSessionId),
			  always: this.initJanus()
		  });
      }	
  }
});