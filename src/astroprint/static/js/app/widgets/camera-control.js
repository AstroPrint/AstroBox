var CameraControlView = Backbone.View.extend({
  el: null,
  serverUrl: null,
  localSessionId: null,
  streamingPlugIn: null,
  events: {
	'hide':'onHide'
  },
  settings: null,
  cameraAvailable: null,
  ableWebRtc: null,//['ready','nowebrtc']
  print_capture: null,
  photoSeq: 0,
  cameraModeByValue: function(value){
  	/* Values matches by options:
    * - True: video mode
    * - False: photo mode
    */
  	mode = value?'video':'photo';

  	return mode;
  },
  cameraMode: 'video',//['video','photo']
  initialize: function(parameters)
  {
	
	$.post(API_BASEURL + 'camera/is-camera-available')
	.done(_.bind(function(response){
			
		this.cameraAvailable = response.isCameraAvailable;

		if(this.cameraAvailable){

			//video settings
			if( !parameters || ! parameters.settings ){
				
				$.getJSON(API_BASEURL + 'settings/camera/streaming')
				.done(_.bind(function(settings){
					
					this.settings = settings;
					
					this.evalWebRtcAbleing();

				},this));

			} else {
				this.settings = parameters.settings;
				this.evalWebRtcAbleing();
			}
		} else { this.render(); }
	},this))
  },
  evalWebRtcAbleing: function(){
  	if(Janus.isWebrtcSupported()) {
		if(!(navigator.mozGetUserMedia) 
				&&
			!(this.settings.encoding == 'vp8')
		){
			//BROWSER IS NOT FIREFOX
			//AND VIDEO IS NOT VP8
			
			//this.setState('nowebrtc');
			//this.ableWebRtc = false;
			
			this.$('#camera-mode-slider').hide();
			this.ableWebRtc = false;
			
			////////////////////////
		} else {
			this.setState('ready'); 
			this.ableWebRtc = true;
		}
	} else {
		this.setState('nowebrtc');
		this.ableWebRtc = false;
	}

	if( !this.ableWebRtc){
		this.initJanus = null;
		this.startStreaming = function(){ this.setState('nowebrtc'); };
		this.stopStreaming = function(){ return true; };
		this.onHide = function(){ return true; };
		//this.setState('nowebrtc');
		this.cameraMode = 'photo';
	} else {
		this.serverUrl = "http://" + window.location.hostname + ":8088/janus";
		startStreaming = this.startStreaming;
		this.initJanus();

		// Initialize the library (all console debuggers enabled)
		Janus.init({debug: "all", callback: function() {
			console.log('Janus Initialized')
		}});
	}
	this.render();
  },
  onHide: function(){
 	this.stopStreaming();
  },
  buttonEvent: function(e,text){
  	if(this.cameraMode == 'video'){
  		if(this.state == 'streaming'){
  			this.stopStreaming();
  		} else {
  			this.startStreaming();
  		}
  	} else { //photo
  		this.takePhoto(text);
  	}
  },
  takePhoto: function(text) {

  	$('.icon-3d-object').hide();

  	this.$('.loading-button').addClass('loading');

  	setTimeout(_.bind(function(){

	  	var queryParams = [
	  		"timestamp=" + (Date.now() / 1000)
	  	];

	  	if (text) {
	  		queryParams.push("text="+encodeURIComponent(text));
	  	}

	  	this.$('.camera-image').attr('src', '/camera/snapshot?' + queryParams.join("&"));

	  	
		this.$('.camera-image').load(_.bind(function() {
	    	this.$('.loading-button').removeClass('loading');
		},this));
  	},this),100);

  },
  initJanus: function(){
  	this.localSessionId = null;
	this.streamingPlugIn = null;
  },
  setState: function(state)
  {
  	this.state = state;
	this.$el.removeClass('preparing error nowebrtc streaming ready').addClass(state)  
  },
  startStreaming: function(e){	  
  	
	this.setState('preparing');
	$.ajax({
			url: API_BASEURL + "camera/init-janus",
			type: "POST",
			dataType: "json",
			contentType: "application/json; charset=UTF-8",
			data: ''
	})
	.done(_.bind(function(isJanusRunning){
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
						var selectedStream = this.settings.encoding == 'h264' ? 1 : 2;
						console.log('Starting ' + this.settings.encoding);
						var sizeVideo = this.settings.size;

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
									url: API_BASEURL + "camera/start-streaming",
									type: "POST"
								}).fail(_.bind(function(){console.log('ERROR');this.setState('error');},this));
			                    window.setTimeout(_.bind(function(){
			                    	console.log('Timeout!!!');
			                    	if(!isPlaying){
			                    		console.log('Stop Janus caused by timeout!!!');
			                    		this.stopStreaming();
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
				error: _.bind(function(error) {
					if(!this.$el.hasClass('ready')){
						console.error(error);
						noty({text: "Unable to start the WebRTC session.", timeout: 3000});
						//This is a fatal error. The application can't recover. We should probably show an error state in the app.
						streamingState = 'stopped';
					}
				},this),
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
