var CameraView = Backbone.View.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  serverUrl: null,
  localSessionId: null,
  streamingPlugIn: null,
  events: {
	'click .buttons .columns .success': 'startStreaming',
	'click .buttons .columns .secondary': 'stopStreaming',
	'hide':'onHide'
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
	
	if(Janus.isWebrtcSupported()) {
		this.setState('ready');
	} else {
		this.setState('nowebrtc');
	}
  },
  render: function() {
	this.$el.html(this.template());
  },
  onHide: function(){
 	this.stopStreaming();
  },
  initJanus: function(){
  	this.localSessionId = null;
	this.streamingPlugIn = null;
  },
  setState: function(state)
  {
	this.$el.removeClass('preparing error nowebrtc streaming ready').addClass(state)  
  },
  startStreaming: function(e){	  
	this.setState('preparing');
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
	.done(_.bind(function(settings, isJanusRunning){
		if(!this.$('#remotevideo').is(':visible')) {			
			// Create session
			var janus = new Janus({
				server: this.serverUrl,
				apisecret: 'd5faa25fe8e3438d826efb1cd3369a50',
				success: _.bind(function() {
					$.ajax({
						url: API_BASEURL + "camera/start-peer-session",
						type: "POST",
						dataType: "json",
						contentType: "application/json; charset=UTF-8",
						data: JSON.stringify()
					}).done(_.bind(function(response) {
						this.localSessionId = response.sessionId;

			            var streamingPlugIn = null;
						var selectedStream = settings[0].encoding == 'h264' ? 1 : 2;
						console.log('Starting '+settings[0].encoding);
						var sizeVideo = settings.size;

						//Attach to streaming plugin
						janus.attach({
							plugin: "janus.plugin.streaming",
							success: _.bind(function(pluginHandle) {
								this.streamingPlugIn = pluginHandle;
								console.log('Janus Streaming PlugIn Created');
								
								this.streamingPlugIn.oncleanup = _.bind(function(){
									var body = { "request": "destroy" };
				                	this.streamingPlugIn.send({"message": body});

									$.ajax({
					                    url: API_BASEURL + "camera/close-peer-session",
					                    type: "POST",
					                    dataType: "json",
					                    contentType: "application/json; charset=UTF-8",
					                    data: JSON.stringify({
					                    	sessionId: this.localSessionId
					                    })
					                })
				                    .done(_.bind(function(){
				                    	this.setState('ready');
				                    	janus.sessionId = null;
				                    },this))
				                    .always(_.bind(this.initJanus, this))
				                    .fail(_.bind(function(){this.setState('error');},this))
				                },this);

				                var body = { "request": "watch", id: selectedStream };
				                this.streamingPlugIn.send({"message": body});
							},this),
							error: function(error) {
								console.error(error);
								noty({text: "Error communicating with the WebRTC system.", timeout: 3000});
							},
							onmessage: _.bind(function(msg, jsep) {
								//console.log(" ::: Got a message :::");
								//console.log(JSON.stringify(msg));
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
										//Answer
										this.streamingPlugIn.createAnswer(
										{
											jsep: jsep,
											media: { audioSend: false, videoSend: false },	// We want recvonly audio/video
											success: _.bind(function(jsep) {
												var body = { "request": "start" };
												this.streamingPlugIn.send({"message": body, "jsep": jsep});
											},this),
											error: _.bind(function(error) {
												console.warn("WebRTC error... " + JSON.stringify(error));
												this.setState('error');
											},this)
										});
									}
							}, this),
							onremotestream: _.bind(function(stream) {
								//Starts GStreamer
								$.ajax({
									//url: API_BASEURL + "camera/stop-janus",
									url: API_BASEURL + "camera/start-streaming",
									type: "POST"
								}).fail(_.bind(function(){console.log('ERROR');this.setState('error');},this));
			                    window.setTimeout(_.bind(function(){
			                    	console.log('Timeout!!!');
			                    	if(!isPlaying){
			                    		console.log('Stop Janus caused by timeout!!!');
			                    		//this.stopStreaming();
							this.setState('error');
			                    	}
			                    },this),40000);
			                    var isPlaying = false;
			                    $("#remotevideo").bind("playing",_.bind(function () {
			                    	this.setState('streaming');
			                    	isPlaying = true;
			                    },this));
			                    attachMediaStream($('#remotevideo').get(0), stream);
							},this),
							oncleanup: function() {
								Janus.log(" ::: Got a cleanup notification :::");
							}
						});
						},this)
					);
				}, this),
				error: function(error) {
					if(!$('#camera-view').hasClass('ready')){
						console.error(error);
						noty({text: "Unable to start the WebRTC session.", timeout: 3000});
						//This is a fatal error. The application can't recover. We should probably show an error state in the app.
						streamingState = 'stopped';
					}
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
	if (this.localSessionId) { 
		var body = { "request": "stop" };
		this.streamingPlugIn.send({"message": body});
	}	
	
  }
});
