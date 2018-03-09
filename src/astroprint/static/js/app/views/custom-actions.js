var CustomActionsView = Backbone.View.extend({
  el: '#custom-actions-view',
  customActionsListView: null,
  initialize: function()
  {
    this.customActionsListView = new CustomActionsListView();
  }
});


// Custom actions menu
var CustomActionsListView = Backbone.View.extend({
  el: '#action-list',
  customAction_views: [],
  customizedActionCollection: null,
  initialize: function()
  {
    this.customizedActionCollection = new CustomizedActionCollection();
    //this.customizedActionCollection = 'name'
    $.getJSON(API_BASEURL + 'custom-actions', null, _.bind(function(data) {

      if (data.utilities && data.utilities.length) {
        for (var i = 0; i < data.utilities.length; i++) {
          let ca = data.utilities[i];
          if (ca.visibility) {
            this.customizedActionCollection.add(new CustomizedAction(ca))
          }
        }
        this.render();
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting customized commands.", timeout: 3000});
    })
  },
  render: function()
  {
    // Render each box
    this.customizedActionCollection.each(function (customActionApp) {
      var row = new CustomActionRowView({ customActionApp: customActionApp});
      this.$el.append(row.render().el);
      this.customAction_views[customActionApp.get('id')] = row;
    }, this);
  }
});

var CustomActionRowView = Backbone.View.extend({
  className: 'action-row',
  tagName: 'li',
  customActionApp: null,
  template: _.template($("#action-row-template").html()),
  initialize: function (params)
  {
    this.customActionApp = params.customActionApp;
    this.$el.attr('id', this.customActionApp.get('id'));
  },
  render: function ()
  {
    this.$el.empty();
    this.$el.html(this.template({ view: this, customActionApp: this.customActionApp.toJSON() }));
    return this;
  }
});




