$.ajaxSetup({
  cache: false,
  headers: {
    "X-Api-Key": UI_API_KEY
  }
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
      data: this.$el.serializeArray()
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

var form = new LoginForm();
