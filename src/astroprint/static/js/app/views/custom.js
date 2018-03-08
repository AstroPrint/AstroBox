var CustomView = Backbone.View.extend({
  el: '#custom-view',
  actionList: null,
	initialize: function() {
    this.actionListView = new CustomActionListView();
  }
});

var CustomActionListView = Backbone.View.extend({
  el: '#action-list',
  customAction_views: [],
  customizedActionCollection: null,
  initialize: function() {
    this.customizedActionCollection = new CustomizedActionCollection();
    //this.customizedActionCollection = 'name'
    $.getJSON(API_BASEURL + 'custom-commands', null, _.bind(function(data) {

      if (data.utilities && data.utilities.length) {
        for (var i = 0; i < data.utilities.length; i++) {
          let ca = data.utilities[i];
          if (ca.visibility) {
            this.customizedActionCollection.add(new CustomizedAction(ca))
          }
        }
        this.render();
        console.log('COLLECTION', this.customizedActionCollection);
      } else {
        console.log('There is no customized commands');
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting customized commands.", timeout: 3000});
    })
  },
  render: function() {
    // Render each box
    this.customizedActionCollection.each(function (customAction) {
      var row = new CustomActionRowView({ customAction: customAction});
      this.$el.append(row.render().el);
      this.customAction_views[customAction.get('id')] = row;
    }, this);
  }
});

var CustomActionRowView = Backbone.View.extend({
  className: 'action-row',
  tagName: 'li',
  customAction: null,
  template: _.template($("#action-row-template").html()),
  initialize: function (params) {
    this.customAction = params.customAction;
    console.log( this.customAction);
    this.$el.attr('id', this.customAction.get('id'));
  },
  render: function ()
  {
    this.$el.empty();
    this.$el.html(this.template({ view: this, customAction: this.customAction.toJSON() }));
    return this;
  },
});
