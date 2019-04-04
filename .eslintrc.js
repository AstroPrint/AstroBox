module.exports = {
  "env": {
      "browser": true,
      "jquery": true,
      "es6": false
  },
  "extends": "eslint:recommended",
  "globals": {
      "_": "readonly",
      "Backbone": "readonly",
      "SockJS": "readonly",
      "app": "readonly",
      "noty": "readonly",
      "FileUploadBase": "readonly",
      "FileUploadCombined": "readonly",
      "initial_states": "readonly",
      "initial_printer_profile": "readonly",
      "API_BASEURL": "readonly",
      "ASTROBOX_NAME": "readonly",
      "LOGGED_USER": "readonly",
      "SOCKJS_DEBUG": "readonly",
      "SOCKJS_URI": "readonly",
      "PRODUCT_NAME": "readonly",
      "CAMERA_MANAGER": "readonly",
      "WS_TOKEN": "readonly",
      "UI_API_KEY": "readonly",
      "AP_SESSION_ID": "readonly",
  },
  "parserOptions": {
      "ecmaVersion": 5
  },
  "rules": {
    "no-console": ["error", {"allow": ["warn", "error"]}]
  }
};
