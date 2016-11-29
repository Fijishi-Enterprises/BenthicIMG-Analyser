var AnnotationToolImageHelper = (function() {

    var $applyButton = null;
    var $resetButton = null;
    var $applyingText = null;

    var form = null;
    var fields = null;

    var MIN_BRIGHTNESS = -100;
    var MAX_BRIGHTNESS = 100;
    var BRIGHTNESS_STEP = 1;

    var MIN_CONTRAST = -100;
    var MAX_CONTRAST = 100;
    var CONTRAST_STEP = 1;

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
        if (currentSourceImage === null)
            return;

        // If processing is currently going on, emit the redraw signal to
        // tell it to stop processing and re-call this function.
        if (nowApplyingProcessing === true) {
            redrawSignal = true;
            return;
        }

        // Redraw the source image.
        imageCanvas.getContext("2d").drawImage(currentSourceImage.imgBuffer, 0, 0);

        // If processing parameters are the default values, then we just need
        // the original image, so we're done.
        if (fields.brightness.value === fields.brightness.defaultValue
           && fields.contrast.value === fields.contrast.defaultValue) {
            return;
        }

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

        // The user-defined brightness and contrast are applied as
        // 'bias' and 'gain' according to this formula:
        // http://docs.opencv.org/2.4/doc/tutorials/core/basic_linear_transform/basic_linear_transform.html

        // We'll say the bias can increase/decrease the pixel value by
        // as much as 150.
        var brightness = Number(fields.brightness.value);
        var brightnessFraction =
            (brightness - MIN_BRIGHTNESS) / (MAX_BRIGHTNESS - MIN_BRIGHTNESS);
        var bias = (150*2)*brightnessFraction - 150;

        // We'll say the gain can multiply the pixel values by
        // a range of MIN_BIAS to MAX_BIAS.
        // The middle contrast value must map to 1.
        var MIN_BIAS = 0.25;
        var MAX_BIAS = 3.0;
        var contrast = Number(fields.contrast.value);
        var contrastFraction =
            (contrast - MIN_CONTRAST) / (MAX_CONTRAST - MIN_CONTRAST);
        var gain = null;
        var gainFraction = null;
        if (contrastFraction > 0.5) {
            // Map 0.5~1.0 to 1.0~3.0
            gainFraction = (contrastFraction - 0.5) / (1.0 - 0.5);
            gain = (MAX_BIAS-1.0)*gainFraction + 1.0;
        }
        else {
            // Map 0.0~0.5 to 0.25~1.0
            gainFraction = contrastFraction / 0.5;
            gain = (1.0-MIN_BIAS)*gainFraction + MIN_BIAS;
        }

        applyBriConToRemainingRects(gain, bias, rects);
    }

    function applyBriConToRect(gain, bias, data, numPixels) {
        // Performance note: We tried having a curried function which was
        // called once for each pixel. However, this ended up taking 8-9
        // seconds for a 1400x1400 pixel rect, even if the function simply
        // returns immediately. (Firefox 50.0, 2016.11.28)
        // So the lesson is: function calls are usually cheap,
        // but don't underestimate using them by the million.
        var px;
        for (px = 0; px < numPixels; px++) {
            // 4 components per pixel, in RGBA order. We'll ignore alpha.
            data[4*px] = gain*data[4*px] + bias;
            data[4*px + 1] = gain*data[4*px + 1] + bias;
            data[4*px + 2] = gain*data[4*px + 2] + bias;
        }
    }

    function applyBriConToRemainingRects(gain, bias, rects) {
        if (redrawSignal === true) {
            nowApplyingProcessing = false;
            redrawSignal = false;
            $applyingText.css({'visibility': 'hidden'});

            redrawImage();
            return;
        }

        // "Pop" the first element from rects.
        var rect = rects.shift();

        // Grab the rect from the image canvas.
        var rectCanvasImageData = imageCanvas.getContext("2d")
            .getImageData(rect.left, rect.top, rect.width, rect.height);

        // Apply bri/con to the rect.
        applyBriConToRect(
            gain, bias, rectCanvasImageData.data,
            rect['width']*rect['height']);

        // Put the post-bri/con data on the image canvas.
        imageCanvas.getContext("2d").putImageData(
            rectCanvasImageData, rect.left, rect.top);

        if (rects.length > 0) {
            // Slightly delay the processing of the next rect, so we
            // don't lock up the browser for an extended period of time.
            // Note the use of curry() to produce a function.
            setTimeout(
                applyBriConToRemainingRects.curry(gain, bias, rects), 50
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
