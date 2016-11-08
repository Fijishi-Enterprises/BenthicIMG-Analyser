Browser compatibility
=====================

This table largely excludes old Firefox/Chrome versions, old mobile browser versions, and IE 6 or earlier. This table may go slightly beyond currently-common versions for informational purposes.

Although we tend to recommend the latest Firefox/Chrome, we should still weigh support of other common browsers versus the usefulness of a particular feature. For Javascript, consider using polyfills if they're not too large.

.. list-table::

   * - Feature used on CoralNet
     - Incompatible browsers
     - Usage notes
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
   * - `:not selector <http://caniuse.com/#feat=css-sel3>`__
     - Safari 3.1, IE 8
     -