.SILENT:

CURRENT_TIME := $(shell date -u +"%Y-%m-%d %H:%M:%S")
DATE_APPEND := $(shell date -u +"%Y%m%d")

#App JS Files

JS_APP_FILES := lib/jquery.js lib/jquery.ui.widget.js lib/underscore.js lib/backbone.js lib/foundation/foundation.js lib/foundation/foundation.offcanvas.js lib/foundation/foundation.reveal.js \
				lib/sockjs.js lib/fastclick.js lib/jquery.fileupload.js lib/jquery.noty.js lib/jquery.noty.top.js \
				app/models/socketdata.js app/models/printfiles.js \
				app/utils.js \
				app/views/home.js app/views/control.js app/views/settings.js app/views/connection.js app/views/turnoff.js app/views/printing.js app/router.js \
				app/app.js

JS_APP_LIST := 	$(foreach file, $(JS_APP_FILES), \
					$(addprefix src/astroprint/static/js/, $(file)) \
				)
JS_APP_PACKED := src/astroprint/static/js/gen/app.js

#Login JS Files

JS_LOGIN_FILES := 	lib/foundation/foundation.abide.js app/login.js

JS_LOGIN_LIST := 	$(foreach file, $(JS_LOGIN_FILES), \
						$(addprefix src/astroprint/static/js/, $(file)) \
					)	
JS_LOGIN_PACKED := src/astroprint/static/js/gen/login.js 

#Setup JS Files

JS_SETUP_FILES := 	lib/jquery.js lib/underscore.js lib/backbone.js lib/fastclick.js lib/foundation/foundation.js lib/foundation/foundation.abide.js lib/foundation/foundation.reveal.js \
					lib/jquery.noty.js lib/jquery.noty.top.js lib/sockjs.js \
					setup/setup.js

JS_SETUP_LIST := 	$(foreach file, $(JS_SETUP_FILES), \
						$(addprefix src/astroprint/static/js/, $(file)) \
					)	
JS_SETUP_PACKED := src/astroprint/static/js/gen/setup.js 

#Updating JS Files

JS_UPDATING_FILES := 	lib/jquery.js lib/underscore.js lib/backbone.js lib/sockjs.js lib/fastclick.js updating/updating.js

JS_UPDATING_LIST := 	$(foreach file, $(JS_UPDATING_FILES), \
							$(addprefix src/astroprint/static/js/, $(file)) \
						)	
JS_UPDATING_PACKED := src/astroprint/static/js/gen/updating.js 

#CSS Files

CSS_APP_FILE := src/astroprint/static/css/scss/app.scss
CSS_APP_PACKED := src/astroprint/static/css/gen/app.css

CSS_LOGIN_FILE := src/astroprint/static/css/scss/login.scss
CSS_LOGIN_PACKED := src/astroprint/static/css/gen/login.css

CSS_SETUP_FILE := src/astroprint/static/css/scss/setup.scss
CSS_SETUP_PACKED := src/astroprint/static/css/gen/setup.css

CSS_UPDATING_FILE := src/astroprint/static/css/scss/updating.scss
CSS_UPDATING_PACKED := src/astroprint/static/css/gen/updating.css

#rules

all: js css python

clean: clean-js clean-css clean-python clean-release

release: clean-release clean-js clean-css js css python
	echo "Creating release..."
	mkdir -p build/debian
	cp -r debian/* build/debian

	mkdir -p build/debian/AstroBox
	cp -p run build/debian/AstroBox/run
	cp -p requirements.txt build/debian/AstroBox/requirements.txt
	cp -rfp src build/debian/AstroBox/src

	echo "Copying install scripts"
	cp -p debian/Makefile build/debian/AstroBox/Makefile

	echo "Setting time stamps to $(CURRENT_TIME)"

	sed -i "" -e 's/<BUILD_TIME>/"$(CURRENT_TIME)"/g' build/debian/usr/bin/astrobox-init

	echo "Cleaning unnecessary files..."
	find build/debian/AstroBox/src -name "*.py" -type f -delete
	find build/debian/AstroBox/src -name "*.pyc" -type f -delete
	find build/debian/AstroBox/src -name ".DS_Store" -type f -delete
	find build/debian/AstroBox/src -name "empty" -type f -delete
	rm -rf build/debian/AstroBox/src/astroprint/static/.webassets*
	rm -rf build/debian/AstroBox/src/astroprint/static/js/app
	rm -rf build/debian/AstroBox/src/astroprint/static/js/lib
	rm -rf build/debian/AstroBox/src/astroprint/static/css/scss
	rm -rf build/debian/AstroBox/src/octoprint/templates
	rm -rf build/debian/AstroBox/src/octoprint/static

	echo "Creating debian package"
	fakeroot -- dpkg-deb -b build/debian
	
	mv build/debian.deb build/AstroBox_$(DATE_APPEND).deb
	echo "Release at " $(PWD)/build/AstroBox_$(DATE_APPEND).deb

js: $(JS_APP_PACKED) $(JS_LOGIN_PACKED) $(JS_SETUP_PACKED) $(JS_UPDATING_PACKED)

css: $(CSS_APP_PACKED) $(CSS_LOGIN_PACKED) $(CSS_SETUP_PACKED) $(CSS_UPDATING_PACKED)

python: 
	echo "Generating .pyo files..."
	python -OO -m compileall src

$(JS_APP_PACKED): $(JS_APP_LIST)
	echo "Packing app javascript..."
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(JS_LOGIN_PACKED): $(JS_LOGIN_LIST)
	echo "Packing login javascript..."
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(JS_SETUP_PACKED): $(JS_SETUP_LIST)
	echo "Packing setup javascript..."
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(JS_UPDATING_PACKED): $(JS_UPDATING_LIST)
	echo "Packing updating javascript..."
	closure \
		--warning_level QUIET \
		--language_in ECMASCRIPT5 \
		--compilation_level SIMPLE_OPTIMIZATIONS \
		--js $^ \
		--js_output_file $@

$(CSS_APP_PACKED): $(CSS_APP_FILE)
	echo "Packing App CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/astroprint/static/css/scss $@ 

$(CSS_LOGIN_PACKED): $(CSS_LOGIN_FILE)
	echo "Packing Login CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/astroprint/static/css/scss $@ 

$(CSS_SETUP_PACKED): $(CSS_SETUP_FILE)
	echo "Packing Setup CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/astroprint/static/css/scss $@ 

$(CSS_UPDATING_PACKED): $(CSS_SETUP_FILE)
	echo "Packing Updating CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/astroprint/static/css/scss $@ 

clean-js:
	rm -f $(JS_APP_PACKED) $(JS_LOGIN_PACKED) $(JS_SETUP_PACKED) $(JS_UPDATING_PACKED)

clean-css:
	rm -f $(CSS_APP_PACKED) $(CSS_LOGIN_PACKED) $(CSS_SETUP_PACKED) $(CSS_UPDATING_PACKED)

clean-python:
	find src/octoprint -name "*.pyo" -type f -delete
	find src/astroprint -name "*.pyo" -type f -delete

clean-release:
	rm -rf build
	rm -rf debian/AstroBox
