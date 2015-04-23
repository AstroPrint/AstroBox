/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var FileUploadDashboard = FileUploadCombined.extend({
	container: null,
	circleProgress: null,
	initialize: function(options)
	{
		FileUploadCombined.prototype.initialize.call(this, options);

		this.container = this.$el.closest('.upload-btn');		
	},
	started: function(data)
	{
		if (data.files && data.files.length > 0) {
			this.container.addClass('uploading');

			FileUploadCombined.prototype.started.call(this, data);

			if (this.circleProgress === null) {
				var progressContainer = this.container.find('.app-image');

				this.circleProgress = this.container.find(".progress").circleProgress({
			        value: 0,
			        animation: false,
			        size: progressContainer.innerWidth() - 12,
			        fill: { color: 'white' }
		    	});

				$(window).bind('resize', _.bind(function() {
					if (this.container.hasClass('uploading')) {
						this.circleProgress.circleProgress({size: progressContainer.innerWidth() - 12});
					}
				}, this));
			}
		}
	},
	progress: function(progress)
	{
		this.container.find('.progress span').html(Math.round(progress)+'<i>%</i>');
		this.circleProgress.circleProgress({value: progress / 100.0});
	},
	failed: function(error)
	{
		this.container.addClass('failed').removeClass('uploading');

		setTimeout(_.bind(function(){
			this.container.removeClass('failed');
		}, this), 3000);
		console.error(error);
	},
	success: function(data)
	{
		FileUploadCombined.prototype.success.call(this, data);

		if (this.currentFileType != 'design') {
			this.container.removeClass('uploading');
		}
	}
});

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadBtn: null,
	initialize: function()
	{
		this.uploadBtn = new FileUploadDashboard({el: "#home-view #app-container .upload-btn .file-upload"});
	}
});