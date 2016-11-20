$.ajaxSetup({
  cache: false
});

LoginForm = Backbone.View.extend({
  el: '#login-form',
  events: {
    'submit': 'onSubmit'
  },
  onSubmit: function(e)
  {
    e.preventDefault();

    var loadingBtn = this.$('.loading-button');

    loadingBtn.addClass('loading');

    $.ajax({
      type: 'POST',
      url: '/api/login',
      data: this.$el.serializeArray(),
      headers: {
        "X-Api-Key": UI_API_KEY
      }
    })
    .done(function(){
      location.reload();
    })
    .fail(function(xhr){
      var message = "Unkonwn error. Please refresh the page";

      if (xhr.status == 401) {
        if (xhr.responseText.toLowerCase() == 'invalid api key') {
          message = "The access key has changed. Please refresh the page.";
        } else {
          message = "Invalid Password";
        }
      }

      noty({text: message , timeout: 3000});
      loadingBtn.removeClass('loading');
    });

    return false;
  }
});

LockedView = Backbone.View.extend({
  form: null,
  initialize: function()
  {
    this.form = new LoginForm();
    this.startPolling();
  },
  startPolling: function()
  {
    setInterval(_.bind(function(){
      $.ajax({type:'POST', url: '/accessKeys'})
        .done(function(data){
          if (_.isObject(data)) {
            location.reload();
          }
        })
    }, this), 3000);
  }
});

var lockedVide = new LockedView();
