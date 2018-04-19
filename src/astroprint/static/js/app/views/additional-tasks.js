var AdditionalTasksView = Backbone.View.extend({
  el: '#additional-tasks-view',
  additionalTasksListView: null,
  initialize: function()
  {
    this.additionalTasksListView = new AdditionalTasksListView();
  }
});


// Custom actions menu
var AdditionalTasksListView = Backbone.View.extend({
  el: '#task-list',
  additionalTask_views: [],
  additionalTaskCollection: null,
  initialize: function()
  {
    this.additionalTaskCollection = new AdditionalTaskCollection();
    //this.additionalTaskCollection = 'name'
    $.getJSON(API_BASEURL + 'additional-tasks', null, _.bind(function(data) {


      if (data.utilities && data.utilities.length) {
        for (var i = 0; i < data.utilities.length; i++) {
          var adTask = data.utilities[i];
          if (adTask.visibility) {
            this.additionalTaskCollection.add(new AdditionalTask(adTask))
          }
        }
        this.render();
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting additional tasks.", timeout: 3000});
    })
  },
  render: function()
  {
    // Render each box
    this.additionalTaskCollection.each(function (additionalTaskApp) {
      var row = new AdditionalTaskRowView({ additionalTaskApp: additionalTaskApp});
      this.$el.append(row.render().el);
      this.additionalTask_views[additionalTaskApp.get('id')] = row;
    }, this);
  }
});

var AdditionalTaskRowView = Backbone.View.extend({
  className: 'task-row',
  tagName: 'li',
  additionalTaskApp: null,
  template: _.template($("#task-row-template").html()),
  initialize: function (params)
  {
    this.additionalTaskApp = params.additionalTaskApp;
    this.$el.attr('id', this.additionalTaskApp.get('id'));
  },
  render: function ()
  {
    this.$el.empty();
    this.$el.html(this.template({ view: this, additionalTaskApp: this.additionalTaskApp.toJSON() }));
    return this;
  }
});




