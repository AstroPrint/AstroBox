.SILENT:

#App JS Files

JS_APP_FILES := lib/jquery.js lib/underscore.js lib/backbone.js lib/foundation/foundation.js lib/foundation/foundation.offcanvas.js lib/foundation/foundation.reveal.js lib/sockjs.js lib/fastclick.js \
				app/models/socketdata.js \
				app/views/home.js app/views/control.js app/views/settings.js app/views/connection.js app/views/turnoff.js \
				app/app.js
JS_APP_LIST := 	$(foreach file, $(JS_APP_FILES), \
					$(addprefix src/octoprint/astrobox-app/js/, $(file)) \
				)
JS_APP_PACKED := src/octoprint/astrobox-app/js/gen/app.js

#Login JS Files

JS_LOGIN_FILES := 	lib/jquery.js lib/underscore.js lib/backbone.js lib/foundation/foundation.js lib/foundation/foundation.abide.js \
					app/views/login.js

JS_LOGIN_LIST := 	$(foreach file, $(JS_LOGIN_FILES), \
						$(addprefix src/octoprint/astrobox-app/js/, $(file)) \
					)	
JS_LOGIN_PACKED := src/octoprint/astrobox-app/js/gen/login.js 

#CSS Files

CSS_FILES := app.scss login.scss
CSS_LIST := $(foreach file, $(CSS_FILES), \
				$(addprefix src/octoprint/astrobox-app/css/scss/, $(file)) \
			)
CSS_PACKED := src/octoprint/astrobox-app/css/gen/main.css

#rules

all: js css python release

clean: clean-js clean-css clean-python clean-release

release:
	echo "Cleaning build directory..."
	rm -rf build
	echo "Creating release..."
	mkdir -p build/AstroBox
	cp -p run build/AstroBox/run
	cp -p requirements.txt build/AstroBox/requirements.txt
	cp -rfp src build/AstroBox/src
	echo "Cleaning unnecessary files..."
	find build/AstroBox/src -name "*.py" -type f -delete
	find build/AstroBox/src -name "*.pyc" -type f -delete
	find build/AstroBox/src -name ".DS_Store" -type f -delete
	find build/AstroBox/src -name "empty" -type f -delete
	rm -r build/AstroBox/src/octoprint/astrobox-app/.webassets*
	rm -r build/AstroBox/src/octoprint/astrobox-app/js/app
	rm -r build/AstroBox/src/octoprint/astrobox-app/js/lib
	rm -r build/AstroBox/src/octoprint/astrobox-app/css/scss
	rm -r build/AstroBox/src/octoprint/templates
	rm -r build/AstroBox/src/octoprint/static
	cd build; zip -rq AstroBox-release.zip AstroBox; cd ..
	echo "Release at " $(PWD)/build/AstroBox-release.zip

js: $(JS_APP_PACKED) $(JS_LOGIN_PACKED)

css: $(CSS_PACKED)

python: 
	echo "Generating .pyo files..."
	python -OO -m compileall src

$(JS_APP_PACKED): $(JS_APP_LIST)
	echo "Packing javascript..."
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(JS_LOGIN_PACKED): $(JS_LOGIN_LIST)
	echo "Packing javascript..."
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(CSS_PACKED): $(CSS_LIST)
	echo "Packing CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/octoprint/astrobox-app/css/scss $@ 

clean-js:
	rm -f $(JS_APP_PACKED) $(JS_LOGIN_PACKED)

clean-css:
	rm -f $(CSS_PACKED)

clean-python:
	find src/octoprint -name "*.pyo" -type f -delete

clean-release:
	rm -rf build
