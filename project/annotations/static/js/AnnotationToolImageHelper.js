var AnnotationToolImageHelper = (function() {

    var $applyButton = null;
    var $resetButton = null;
    var $applyingText = null;

    var form = null;
    var fields = null;

    var MIN_BRIGHTNESS = -150;
    var MAX_BRIGHTNESS = 150;
    var BRIGHTNESS_STEP = 1;

    var MIN_CONTRAST = -1.0;
    var MAX_CONTRAST = 3.0;
    var CONTRAST_STEP = 0.1;

    var sourceImages = {};
    var currentSourceImage = null;
    var imageCanvas = null;

    var nowApplyingProcessing = false;
    var redrawSignal = false;


    /* Preload a source image; once it's loaded, swap it in as the image
     * used in the annotation tool.
     *
     * Parameters:
     * code - Which version of the image it is: 'scaled' or 'full'.
     *
     * Basic code pattern from: http://stackoverflow.com/a/1662153/
     */
    function preloadAndUseSourceImage(code) {
        // Create an Image object.
        sourceImages[code].imgBuffer = new Image();

        // When image preloading is done, swap images.
        sourceImages[code].imgBuffer.onload = function() {
            imageCanvas.width = sourceImages[code].width;
            imageCanvas.height = sourceImages[code].height;

            currentSourceImage = sourceImages[code];
            redrawImage();

            // If we just finished loading the scaled image, then start loading
            // the full image.
            if (code === 'scaled') {
                preloadAndUseSourceImage('full');
            }
        };

        // Image preloading starts as soon as we set this src attribute.
        sourceImages[code].imgBuffer.src = sourceImages[code].url;

        // For debugging, it sometimes helps to load an image that
        // (1) has different image content, so you can tell when it's swapped in, and/or
        // (2) is loaded after a delay, so you can zoom in first and then
        //     notice the resolution change when it happens.
        // Here's (2) in action: uncomment the below code and comment out the
        // preload line above to try it.  The second parameter to setTimeout()
        // is milliseconds until the first-parameter function is called.
        // NOTE: only use this for debugging, not for production.
        //setTimeout(function() {
        //    sourceImages[code].imgBuffer.src = sourceImages[code].url;
        //}, 10000);
    }

    /* Redraw the source image, and apply brightness and contrast operations. */
    function redrawImage() {
        // If we haven't loaded any image yet, don't do anything.
        if (currentSourceImage === undefined)
            return;

        // If processing is currently going on, emit the redraw signal to
        // tell it to stop processing and re-call this function.
        if (nowApplyingProcessing === true) {
            redrawSignal = true;
            return;
        }

        // Redraw the source image.
        // (Pixastic has a revert function that's supposed to do this,
        // but it's not really flexible enough for our purposes, so
        // we're reverting manually.)
        imageCanvas.getContext("2d").drawImage(currentSourceImage.imgBuffer, 0, 0);

        // If processing parameters are the default values, then we just need
        // the original image, so we're done.
        if (fields.brightness.value === fields.brightness.defaultValue
           && fields.contrast.value === fields.contrast.defaultValue) {
            return;
        }

        // TODO: Work on reducing browser memory usage.
        // Abandoning Pixastic.process() was probably a good start, since that
        // means we no longer create a new canvas.  What else can be done though?

        /* Divide the canvas into rectangles.  We'll operate on one
           rectangle at a time, and do a timeout between rectangles.
           That way we don't lock up the browser for a really long
           time when processing a large image. */

        var X_MAX = imageCanvas.width - 1;
        var Y_MAX = imageCanvas.height - 1;

        // TODO: Make the rect size configurable somehow.
        var RECT_SIZE = 1400;

        var x1 = 0, y1 = 0, xRanges = [], yRanges = [];
        while (x1 <= X_MAX) {
            var x2 = Math.min(x1 + RECT_SIZE - 1, X_MAX);
            xRanges.push([x1, x2]);
            x1 = x2 + 1;
        }
        while (y1 <= Y_MAX) {
            var y2 = Math.min(y1 + RECT_SIZE - 1, Y_MAX);
            yRanges.push([y1, y2]);
            y1 = y2 + 1;
        }

        var rects = [];
        for (var i = 0; i < xRanges.length; i++) {
            for (var j = 0; j < yRanges.length; j++) {
                rects.push({
                    'left': xRanges[i][0],
                    'top': yRanges[j][0],
                    'width': xRanges[i][1] - xRanges[i][0] + 1,
                    'height': yRanges[j][1] - yRanges[j][0] + 1
                });
            }
        }

        nowApplyingProcessing = true;
        $applyingText.css({'visibility': 'visible'});

        applyBrightnessAndContrastToRects(
            fields.brightness.value,
            fields.contrast.value,
            rects
        )
    }

    function applyBrightnessAndContrastToRects(brightness, contrast, rects) {
        if (redrawSignal === true) {
            nowApplyingProcessing = false;
            redrawSignal = false;
            $applyingText.css({'visibility': 'hidden'});

            redrawImage();
            return;
        }

        // "Pop" the first element from rects.
        var rect = rects.shift();

        var params = {
            image: undefined,  // unused?
            canvas: imageCanvas,
            width: undefined,  // unused?
            height: undefined,  // unused?
            useData: true,
            options: {
                'brightness': brightness,
                'contrast': contrast,
                'rect': rect    // apply the effect to this region only
            }
        };

        // This is a call to an "internal" Pixastic function, sort of.
        // The intended API function Pixastic.process() includes a
        // drawImage() of the entire image, so that's not good for
        // operations that require many calls to Pixastic!
        Pixastic.Actions.brightness.process(params);

        // Now that we've computed the processed-image data, put that
        // data on the canvas.
        // This code block is based on code near the end of the
        // Pixastic core's applyAction().
        if (params.useData) {
            if (Pixastic.Client.hasCanvasImageData()) {
                imageCanvas.getContext("2d").putImageData(params.canvasData, params.options.rect.left, params.options.rect.top);

                // Opera doesn't seem to update the canvas until we draw something on it, lets draw a 0x0 rectangle.
                // Is this still so?
                imageCanvas.getContext("2d").fillRect(0,0,0,0);
            }
        }

        if (rects.length > 0) {
            // Slightly delay the processing of the next rect, so we
            // don't lock up the browser for an extended period of time.
            // Note the use of curry() to produce a function.
            setTimeout(
                applyBrightnessAndContrastToRects.curry(brightness, contrast, rects),
                50
            );
        }
        else {
            nowApplyingProcessing = false;
            $applyingText.css({'visibility': 'hidden'});
        }
    }

    /* Public methods.
     * These are the only methods that need to be referred to as
     * <SingletonClassName>.<methodName>. */
    return {
        init: function (sourceImagesArg) {
            $applyButton = $('#applyImageOptionsButton');
            $resetButton = $('#resetImageOptionsButton');
            $applyingText = $('#applyingText');

            form = util.forms.Form({
                brightness: util.forms.Field({
                    $element: $('#id_brightness'),
                    type: 'signedInt',
                    defaultValue: 0,
                    validators: [util.forms.validators.inNumberRange.curry(MIN_BRIGHTNESS, MAX_BRIGHTNESS)],
                    extraWidget: util.forms.SliderWidget(
                        $('#brightness_slider'),
                        $('#id_brightness'),
                        MIN_BRIGHTNESS,
                        MAX_BRIGHTNESS,
                        BRIGHTNESS_STEP
                    )
                }),
                contrast: util.forms.FloatField({
                    $element: $('#id_contrast'),
                    type: 'signedFloat',
                    defaultValue: 0.0,
                    validators: [util.forms.validators.inNumberRange.curry(MIN_CONTRAST, MAX_CONTRAST)],
                    extraWidget: util.forms.SliderWidget(
                        $('#contrast_slider'),
                        $('#id_contrast'),
                        MIN_CONTRAST,
                        MAX_CONTRAST,
                        CONTRAST_STEP
                    ),
                    decimalPlaces: 1
                })
            });
            fields = form.fields;

            sourceImages = sourceImagesArg;

            imageCanvas = $("#imageCanvas")[0];

            // Initialize fields.
            for (var fieldName in fields) {
                if (!fields.hasOwnProperty(fieldName)) {
                    continue;
                }

                var field = fields[fieldName];

                // Initialize the stored field value.
                field.onFieldChange();
                // When the element's value is changed, update the stored field value
                // (or revert the element's value if the value is invalid).
                field.$element.change(field.onFieldChange);
            }

            if (sourceImages.hasOwnProperty('scaled')) {
                preloadAndUseSourceImage('scaled');
            }
            else {
                preloadAndUseSourceImage('full');
            }

            // When the Apply button is clicked, re-draw the source image
            // and re-apply bri/con operations.
            $applyButton.click(function () {
                redrawImage();
            });

            // When the Reset button is clicked, reset image processing parameters
            // to default values, and redraw the image.
            $resetButton.click(function () {
                for (var fieldName in fields) {
                    if (!fields.hasOwnProperty(fieldName)) {
                        continue;
                    }

                    fields[fieldName].reset();
                }
                redrawImage();
            });
        },

        getImageCanvas: function () {
            return imageCanvas;
        }
    }
})();
