.SILENT:

#App JS Files

JS_APP_FILES := lib/jquery.js lib/jquery.ui.widget.js lib/underscore.js lib/backbone.js lib/foundation/foundation.js lib/foundation/foundation.offcanvas.js lib/foundation/foundation.reveal.js lib/sockjs.js lib/fastclick.js lib/jquery.fileupload.js lib/jquery.noty.js lib/jquery.noty.top.js \
				app/models/socketdata.js app/models/designfiles.js \
				app/views/home.js app/views/control.js app/views/settings.js app/views/connection.js app/views/turnoff.js app/views/printing.js \
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

CSS_APP_FILE := src/octoprint/astrobox-app/css/scss/app.scss
CSS_APP_PACKED := src/octoprint/astrobox-app/css/gen/app.css

CSS_LOGIN_FILE := src/octoprint/astrobox-app/css/scss/login.scss
CSS_LOGIN_PACKED := src/octoprint/astrobox-app/css/gen/login.css

#rules

all: js css python

clean: clean-js clean-css clean-python clean-release

release: clean-release clean-js clean-css js css python
	echo "Creating release..."
	mkdir -p debian/AstroBox
	cp -p run debian/AstroBox/run
	cp -p requirements.txt debian/AstroBox/requirements.txt
	cp -rfp src debian/AstroBox/src

	echo "Copying install scripts"
	cp -p debian/Makefile debian/AstroBox/Makefile
	#mkdir -p build/AstroBox/install
	#cp -rp install/* build/AstroBox/install

	echo "Cleaning unnecessary files..."
	find debian/AstroBox/src -name "*.py" -type f -delete
	find debian/AstroBox/src -name "*.pyc" -type f -delete
	find debian/AstroBox/src -name ".DS_Store" -type f -delete
	find debian/AstroBox/src -name "empty" -type f -delete
	rm -rf debian/AstroBox/src/octoprint/astrobox-app/.webassets*
	rm -rf debian/AstroBox/src/octoprint/astrobox-app/js/app
	rm -rf debian/AstroBox/src/octoprint/astrobox-app/js/lib
	rm -rf debian/AstroBox/src/octoprint/astrobox-app/css/scss
	rm -rf debian/AstroBox/src/octoprint/templates
	rm -rf debian/AstroBox/src/octoprint/static

	echo "Creating debian package"
	fakeroot -- dpkg-deb -b debian

	mkdir build
	mv debian.deb build/AstroBox.deb
	echo "Release at " $(PWD)/build/AstroBox.deb

js: $(JS_APP_PACKED) $(JS_LOGIN_PACKED)

css: $(CSS_APP_PACKED) $(CSS_LOGIN_PACKED)

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

$(CSS_APP_PACKED): $(CSS_APP_FILE)
	echo "Packing App CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/octoprint/astrobox-app/css/scss $@ 

$(CSS_LOGIN_PACKED): $(CSS_LOGIN_FILE)
	echo "Packing Login CSS..."
	cat $^ | scss --stdin --style compressed --load-path src/octoprint/astrobox-app/css/scss $@ 

clean-js:
	rm -f $(JS_APP_PACKED) $(JS_LOGIN_PACKED)

clean-css:
	rm -f $(CSS_APP_PACKED) $(CSS_LOGIN_PACKED)

clean-python:
	find src/octoprint -name "*.pyo" -type f -delete

clean-release:
	rm -rf build
	rm -rf debian/AstroBox
