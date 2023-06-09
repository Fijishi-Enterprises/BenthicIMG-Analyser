Browser compatibility
=====================

The tables largely excludes old Firefox/Chrome versions, old mobile browser versions, and `Internet Explorer <https://blogs.windows.com/windowsexperience/2022/06/15/internet-explorer-11-has-retired-and-is-officially-out-of-support-what-you-need-to-know/>`__.

Although we tend to recommend the latest Firefox/Chrome, we should still weigh support of other browsers versus the usefulness of a particular feature.

If you want your code to check that the user's browser supports a particular feature, it's highly preferred to try and detect the feature itself, rather than using browser-sniffing. For Javascript properties, detect by checking whether they're defined (if not defined, consider defining a polyfill). For Javascript syntax, `detect using eval() <https://stackoverflow.com/questions/23096064/how-can-i-feature-detect-es6-generators>`__.

.. list-table::

   * - Feature used on CoralNet
     - Incompatible browsers
     - Usage notes
   * - `Arrow functions <https://caniuse.com/#feat=arrow-functions>`__
     - IE 11, Samsung Internet 4, Opera Mini
     - Example use: `Using forEach() slightly more concisely <https://stackoverflow.com/a/40364002/>`__
   * - `ES6 Classes <https://caniuse.com/#feat=es6-class>`__
     - IE 11, Samsung Internet 4, Opera Mini
     -
   * - `ES6 Template Literals (Template Strings) <https://caniuse.com/#feat=template-literals>`__
     - IE 11, Opera Mini, UC Browser for Android
     - Our best alternative is ``String.prototype.format()`` defined in ``util.js``
   * - `for...of <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for...of>`__
     - IE 11
     - Don't need the hasOwnProperty() check with this, unlike for...in
   * - `Promises <https://caniuse.com/#feat=promises>`__
     - IE 11, Opera Mini
     - For asynchronous code

Here are some features that aren't yet used, but are fairly likely to be used eventually.

.. list-table::

   * - Feature not used on CoralNet (yet)
     - Incompatible browsers
     - Usage notes
   * - `ES6 Generators <https://caniuse.com/#feat=es6-generators>`__
     - IE 11, Opera Mini
     - Useful for `asynchronous code <http://exploringjs.com/es6/ch_generators.html#sec_overview-generators>`__
