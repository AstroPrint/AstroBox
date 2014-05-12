.SILENT:

JS_FILES := lib/jquery.js lib/underscore.js lib/backbone.js lib/foundation/foundation.js lib/sockjs.js lib/fastclick.js \
			app/models/socketdata.js \
			app/views/control.js app/views/connection.js \
			app/app.js
JS_LIST := 	$(foreach file, $(JS_FILES), \
				$(addprefix src/octoprint/astrobox-app/js/, $(file)) \
			)
JS_PACKED := src/octoprint/astrobox-app/js/gen/packed.js

CSS_FILES := fontello.scss main.scss sprites.scss
CSS_LIST := $(foreach file, $(CSS_FILES), \
				$(addprefix src/octoprint/astrobox-app/css/scss/, $(file)) \
			)
CSS_PACKED := src/octoprint/astrobox-app/css/gen/main.css

all: js css

clean: clean-js clean-css

js: $(JS_PACKED)
css: $(CSS_PACKED)

$(JS_PACKED): $(JS_LIST)
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(CSS_PACKED): $(CSS_LIST)
	cat $^ | scss --stdin --style compressed --load-path src/octoprint/astrobox-app/css/scss $@ 

clean-js:
	rm -f $(JS_PACKED)

clean-css:
	rm -f $(CSS_PACKED)
