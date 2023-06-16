Browser compatibility
=====================

The tables below largely exclude old Firefox/Chrome versions, old mobile browser versions, and `Internet Explorer <https://blogs.windows.com/windowsexperience/2022/06/15/internet-explorer-11-has-retired-and-is-officially-out-of-support-what-you-need-to-know/>`__.

Although we tend to recommend the latest Firefox/Chrome, we should still weigh support of other browsers versus the usefulness of a particular feature.

If you want your code to check that the user's browser supports a particular feature, it's highly preferred to try and detect the feature itself, rather than using browser-sniffing. For Javascript properties, detect by checking whether they're defined (if not defined, consider defining a polyfill). For Javascript syntax, `detect using eval() <https://stackoverflow.com/questions/23096064/how-can-i-feature-detect-es6-generators>`__.

Here are features we use (intentionally, excluding bugs) that are unsupported by an active major browser:

(None)

Here are features that aren't yet used, but are fairly likely to be used eventually:

.. list-table::

   * - Feature not used on CoralNet (yet)
     - Incompatible browsers
     - Usage notes
   * - `CSS Nesting <https://caniuse.com/css-nesting>`__
     - Firefox, as of 114
     - Useful for DRY and maintainability in CSS code

Notable features not in IE 11 include: `Arrow functions <https://caniuse.com/#feat=arrow-functions>`__, `ES6 Classes <https://caniuse.com/#feat=es6-class>`__, `ES6 Generators <https://caniuse.com/#feat=es6-generators>`__, `ES6 Template Literals (Template Strings) <https://caniuse.com/#feat=template-literals>`__, `for...of <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for...of>`__, `Promises <https://caniuse.com/#feat=promises>`__
