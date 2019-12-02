Browser compatibility
=====================

The tables largely excludes old Firefox/Chrome versions, old mobile browser versions, and Internet Explorer 6 or earlier (`IE 6 usage info <https://developer.microsoft.com/en-us/microsoft-edge/ie6countdown/>`__).

Although we tend to recommend the latest Firefox/Chrome, we should still weigh support of other browsers versus the usefulness of a particular feature.

If you want your code to check that the user's browser supports a particular feature, it's highly preferred to try and detect the feature itself, rather than using browser-sniffing. For Javascript properties, detect by checking whether they're defined (if not defined, consider defining a polyfill). For Javascript syntax, `detect using eval() <https://stackoverflow.com/questions/23096064/how-can-i-feature-detect-es6-generators>`__.

.. list-table::

   * - Feature used on CoralNet
     - Incompatible browsers
     - Usage notes
   * - `addEventListener() <http://caniuse.com/#feat=addeventlistener>`__
     - IE 8
     - See `this page <https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/addEventListener>`__ for an explanation of why this is preferred over attributes like ``onclick``.
   * - `Border-radius <http://caniuse.com/#feat=border-radius>`__
     - Opera Mini, IE 8
     - Not a big deal if some elements don't have rounded corners
   * - `Canvas <http://caniuse.com/#search=canvas>`__
     - IE 8
     - No animations used. Annotation tool heavily depends on canvas.
   * - `Child selector <http://caniuse.com/#feat=css-sel2>`__ ``a > b``
     - (None)
     -
   * - `Colors, CSS3 <http://caniuse.com/#feat=css3-colors>`__
     - IE 8
     - ``hsl()`` and ``rgba()`` are used in some places
   * - `Data URIs <http://caniuse.com/#feat=datauri>`__
     - IE 7
     - For lazy-loading of images
   * - `:first-child selector <http://caniuse.com/#feat=css-sel2>`__
     - (None)
     -
   * - `File selection, multiple <http://caniuse.com/#feat=input-file-multiple>`__
     - Android, IE Mobile, Opera Mini, IE 9
     - These browsers should still be able to upload single files on these pages
   * - `Flexbox <http://caniuse.com/#feat=flexbox>`__
     - Safari 8, IE 10
     - Single usage of ``display: flex; align-items: center;`` in map code. Used without ``webkit-`` prefix. (2016.11)
   * - `forEach() <https://caniuse.com/#feat=es5>`__
     - IE 8
     - Replaces the old array for-loop syntax of ``for (i = 0; i < arr.length; i++)``
   * - `input type="number" <http://caniuse.com/#feat=input-number>`__
     - iOS Safari, Android, Chrome for Android, Opera Mini, IE 9
     - Not necessarily broken if not supported, just less robust against arbitrary input.
   * - `:not selector <http://caniuse.com/#feat=css-sel3>`__
     - Safari 3.1, IE 8
     -

Here are some features that aren't yet used, but are fairly likely to be used eventually.

.. list-table::

   * - Feature not used on CoralNet (yet)
     - Incompatible browsers
     - Usage notes
   * - `Arrow functions <https://caniuse.com/#feat=arrow-functions>`__
     - IE 11, Samsung Internet 4, Opera Mini
     - Example use: `Using forEach() slightly more concisely <https://stackoverflow.com/a/40364002/>`__
   * - `ES6 Classes <https://caniuse.com/#feat=es6-class>`__
     - IE 11, Samsung Internet 4, Opera Mini
     -
   * - `ES6 Generators <https://caniuse.com/#feat=es6-generators>`__
     - IE 11, Opera Mini
     - Useful for `asynchronous code <http://exploringjs.com/es6/ch_generators.html#sec_overview-generators>`__
   * - `ES6 Template Literals (Template Strings) <https://caniuse.com/#feat=template-literals>`__
     - IE 11, Opera Mini, UC Browser for Android
     - Our best alternative is ``String.prototype.format()`` defined in ``util.js``
   * - `for...of <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for...of>`__
     - IE 11
     - Don't need the hasOwnProperty() check with this, unlike for...in
   * - `let (variable declaration) <https://caniuse.com/#feat=let>`__
     - Opera Mini
     -
   * - `Promises <https://caniuse.com/#feat=promises>`__
     - IE 11, Opera Mini
     - For asynchronous code
