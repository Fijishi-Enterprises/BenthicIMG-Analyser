var AnnotationToolAutocomplete = (function() {

    var labelCodes = null;
    var machineSuggestions = null;


    /**
     * Get machine suggestions for a set of points. That is, given the fact
     * that these points must all be the same label, we want suggestions
     * for what that label must be.
     * Typically, we're interested in the set of currently-selected points.
     *
     * @param {Number[]} pointList - The set of points to give suggestions for,
     *   specified as an array of point numbers.
     * @return {Object[]} The top suggestions, starting from the best. For each
     *   Object obj, obj.label is a display string like "Porit [45%]", and
     *   obj.value is a label code string like "Porit".
     */
    function getMachineSuggestions(pointList) {

        var lc, pn;
        var label, suggestion, thisPointScore, pointSuggestions;
        // This will map from label codes to confidence scores
        var labelsToScores = {};

        if (pointList.length === 0) {
            // Ensure that no suggestions show when we un-select the last
            // selected point
            return [];
        }
        else if (pointList.length === 1) {
            labelsToScores = machineSuggestions[pointList[0]];
        }
        else {
            // Start off every label with equal scores.
            // We'll modify the scores gradually as we process each point.
            var labelCount = labelCodes.length;
            for (lc = 0; lc < labelCodes.length; lc++) {
                label = labelCodes[lc];
                labelsToScores[label] = 100 / labelCount;
            }

            // Process one point at a time, multiplying probabilities
            // at each iteration.
            for (pn = 0; pn < pointList.length; pn++) {
                var pointNumber = pointList[pn];
                pointSuggestions = machineSuggestions[pointNumber];

                var sumOfScores = 0;

                for (lc = 0; lc < labelCodes.length; lc++) {
                    label = labelCodes[lc];

                    if (pointSuggestions.hasOwnProperty(label)) {
                        // This label is a top suggestion for this point.
                        thisPointScore = pointSuggestions[label];
                    }
                    else {
                        // This label isn't a top suggestion for this point.
                        // We haven't been given the true score, but we'll
                        // just assume 1 (corresponding to 1%). This should
                        // make the probabilities accurate enough.
                        thisPointScore = 1;
                    }
                    labelsToScores[label] *= thisPointScore;
                    sumOfScores += labelsToScores[label];
                }

                // Normalize the scores so that they add up to 100.
                //
                // We do this on each iteration because if we wait until the
                // end of all the points, after doing all of those decimal
                // multiplications, we might go beyond the smallest supported
                // floating point value. (In Chrome 36, that's somewhere
                // around 1e-320 or so.)
                for (label in labelsToScores) {
                    if (!labelsToScores.hasOwnProperty(label)) {continue;}
                    labelsToScores[label] /= (sumOfScores / 100);
                }
            }
        }

        // Make an array of the suggestions,
        // sorted from highest to lowest score
        var suggestionArray = [];
        for (label in labelsToScores) {
            if (!labelsToScores.hasOwnProperty(label)) {continue;}

            suggestionArray.push({
                label: label,
                score: labelsToScores[label]
            });
        }
        suggestionArray.sort(function(a,b){
            if (a['score'] > b['score']) {
                return -1;
            }
            if (a['score'] < b['score']) {
                return 1;
            }
            return 0;
        });
        // Just take the top few scores
        var NUM_OF_SCORES = 5;
        suggestionArray = suggestionArray.slice(0,NUM_OF_SCORES);

        // Format the suggestions for autocomplete
        var suggestionsForWidget = [];
        var s;
        for (s = 0; s < suggestionArray.length; s++) {
            suggestion = suggestionArray[s];
            // Get an integer percentage score, rounding down (36.852% -> 36%).
            //
            // The round-down is to be consistent with Alleviate. To not
            // mislead the user, it should only say 50% if it's going to
            // satisfy a 50% Alleviate threshold, i.e. it's 50.x%.
            var scoreStr = Math.floor(suggestion['score']).toFixed(0);
            suggestionsForWidget.push({
                label: '{0} [{1}%]'.format(suggestion['label'], scoreStr),
                value: suggestion['label']
            });
        }

        return suggestionsForWidget;
    }


    return {

        init: function(params) {

            var $annotationField = params.$annotationField;
            labelCodes = params.labelCodes;

            // machineSuggestions param is in the format
            // [{'label': 'Porit', 'score': 45}, ...] for each point.
            // We'll convert to the format {'Porit': 45, ...} for convenience.
            machineSuggestions = {};
            for (var pointNumber in params.machineSuggestions) {
                if (!params.machineSuggestions.hasOwnProperty(pointNumber)) {
                    continue;
                }

                var oldPointSuggestions = params.machineSuggestions[pointNumber];
                var ps;
                var newPointSuggestions = {};
                for (ps = 0; ps < oldPointSuggestions.length; ps++) {
                    var s = oldPointSuggestions[ps];
                    newPointSuggestions[s['label']] = s['score'];
                }
                machineSuggestions[pointNumber] = newPointSuggestions;
            }

            // Define a custom autocomplete widget.
            $.widget( 'ui.autocomplete', $.ui.autocomplete, {

                // Redefine _create(), copying 90% of it and just changing
                // a couple of handler initializations for our purposes.
                //
                // Base code:
                // https://github.com/jquery/jquery-ui/blob/master/ui/autocomplete.js
                //
                // Yes, this massive code copying is far from ideal, but no
                // better solutions have come to mind.
                _create: function() {
                    // Some browsers only repeat keydown events, not keypress events,
                    // so we use the suppressKeyPress flag to determine if we've already
                    // handled the keydown event. #7269
                    // Unfortunately the code for & in keypress is the same as the up arrow,
                    // so we use the suppressKeyPressRepeat flag to avoid handling keypress
                    // events when we know the keydown event was used to modify the
                    // search term. #7799
                    var suppressKeyPress, suppressKeyPressRepeat, suppressInput,
                        nodeName = this.element[ 0 ].nodeName.toLowerCase(),
                        isTextarea = nodeName === "textarea",
                        isInput = nodeName === "input";

                    this.isMultiLine =
                        // Textareas are always multi-line
                        isTextarea ? true :
                            // Inputs are always single-line, even if inside a contentEditable element
                            // IE also treats inputs as contentEditable
                            isInput ? false :
                                // All other element types are determined by whether or not they're contentEditable
                                this.element.prop( "isContentEditable" );

                    this.valueMethod = this.element[ isTextarea || isInput ? "val" : "text" ];
                    this.isNewMenu = true;

                    this.element
                        .addClass( "ui-autocomplete-input" )
                        .attr( "autocomplete", "off" );

                    this._on( this.element, {
                        keydown: function( event ) {
                            if ( this.element.prop( "readOnly" ) ) {
                                suppressKeyPress = true;
                                suppressInput = true;
                                suppressKeyPressRepeat = true;
                                return;
                            }

                            suppressKeyPress = false;
                            suppressInput = false;
                            suppressKeyPressRepeat = false;
                            var keyCode = $.ui.keyCode;
                            // ANNO-TOOL CHANGE
                            var noKeyModifiers = !event.shiftKey && !event.ctrlKey
                                && !event.altKey && !event.metaKey;

                            switch ( event.keyCode ) {
                                case keyCode.PAGE_UP:
                                    suppressKeyPress = true;
                                    this._move( "previousPage", event );
                                    break;
                                case keyCode.PAGE_DOWN:
                                    suppressKeyPress = true;
                                    this._move( "nextPage", event );
                                    break;
                                case keyCode.UP:
                                    suppressKeyPress = true;
                                    // ANNO-TOOL CHANGE
                                    // Changed to:
                                    // - only fire when no modifiers are pressed
                                    if ( noKeyModifiers ) {
                                        this._keyEvent( "previous", event );
                                    }
                                    else {
                                        // This ensures that the autocomplete
                                        // choices are updated as we use
                                        // Ctrl+up/down to navigate the
                                        // label button grid.
                                        this._searchTimeout( event );
                                    }
                                    break;
                                case keyCode.DOWN:
                                    suppressKeyPress = true;
                                    // ANNO-TOOL CHANGE
                                    // Same changes as keyCode.UP.
                                    if ( noKeyModifiers ) {
                                        this._keyEvent( "next", event );
                                    }
                                    else {
                                        this._searchTimeout( event );
                                    }
                                    break;
                                case keyCode.ENTER:
                                    // when menu is open and has focus
                                    if ( this.menu.active ) {
                                        // #6055 - Opera still allows the keypress to occur
                                        // which causes forms to submit
                                        suppressKeyPress = true;
                                        event.preventDefault();
                                        this.menu.select( event );
                                    }
                                    break;
                                case keyCode.ESCAPE:
                                    if ( this.menu.element.is( ":visible" ) ) {
                                        this._value( this.term );
                                        this.close( event );
                                        // Different browsers have different default behavior for escape
                                        // Single press can mean undo or clear
                                        // Double press in IE means clear the whole form
                                        event.preventDefault();
                                    }
                                    break;
                                default:
                                    suppressKeyPressRepeat = true;
                                    // search timeout should be triggered before the input value is changed
                                    this._searchTimeout( event );
                                    break;
                            }
                        },
                        keypress: function( event ) {
                            if ( suppressKeyPress ) {
                                suppressKeyPress = false;
                                if ( !this.isMultiLine || this.menu.element.is( ":visible" ) ) {
                                    event.preventDefault();
                                }
                                return;
                            }
                            if ( suppressKeyPressRepeat ) {
                                return;
                            }

                            // replicate some key handlers to allow them to repeat in Firefox and Opera
                            var keyCode = $.ui.keyCode;
                            // ANNO-TOOL CHANGE
                            var noKeyModifiers = !event.shiftKey && !event.ctrlKey
                                && !event.altKey && !event.metaKey;

                            switch ( event.keyCode ) {
                                case keyCode.PAGE_UP:
                                    this._move( "previousPage", event );
                                    break;
                                case keyCode.PAGE_DOWN:
                                    this._move( "nextPage", event );
                                    break;
                                case keyCode.UP:
                                    // ANNO-TOOL CHANGE
                                    // Same changes as keydown.
                                    if ( noKeyModifiers ) {
                                        this._keyEvent( "previous", event );
                                    }
                                    break;
                                case keyCode.DOWN:
                                    // ANNO-TOOL CHANGE
                                    // Same changes as keydown.
                                    if ( noKeyModifiers ) {
                                        this._keyEvent( "next", event );
                                    }
                                    break;
                            }
                        },
                        input: function( event ) {
                            if ( suppressInput ) {
                                suppressInput = false;
                                event.preventDefault();
                                return;
                            }
                            this._searchTimeout( event );
                        },
                        focus: function() {
                            this.selectedItem = null;
                            this.previous = this._value();
                        },
                        blur: function( event ) {
                            if ( this.cancelBlur ) {
                                delete this.cancelBlur;
                                return;
                            }

                            clearTimeout( this.searching );
                            this.close( event );
                            this._change( event );
                        }
                    });

                    this._initSource();

                    // ANNO-TOOL CHANGE
                    // Changed .menu( "instance" ); to .data( "ui-menu" );
                    // To prevent an error, as suggested here:
                    // http://forum.jquery.com/topic/issue-with-jquery-ui-selectmenu-no-such-method-instance
                    this.menu = $( "<ul>" )
                        .addClass( "ui-autocomplete ui-front" )
                        .appendTo( this._appendTo() )
                        .menu({
                            // disable ARIA support, the live region takes care of that
                            role: null
                        })
                        .hide()
                        .data( "ui-menu" );

                    this._on( this.menu.element, {
                        mousedown: function( event ) {
                            // prevent moving focus out of the text field
                            event.preventDefault();

                            // IE doesn't prevent moving focus even with event.preventDefault()
                            // so we set a flag to know when we should ignore the blur event
                            this.cancelBlur = true;
                            this._delay(function() {
                                delete this.cancelBlur;
                            });

                            // clicking on the scrollbar causes focus to shift to the body
                            // but we can't detect a mouseup or a click immediately afterward
                            // so we have to track the next mousedown and close the menu if
                            // the user clicks somewhere outside of the autocomplete
                            var menuElement = this.menu.element[ 0 ];
                            if ( !$( event.target ).closest( ".ui-menu-item" ).length ) {
                                this._delay(function() {
                                    var that = this;
                                    this.document.one( "mousedown", function( event ) {
                                        if ( event.target !== that.element[ 0 ] &&
                                            event.target !== menuElement &&
                                            !$.contains( menuElement, event.target ) ) {
                                            that.close();
                                        }
                                    });
                                });
                            }
                        },
                        menufocus: function( event, ui ) {
                            var label, item;
                            // support: Firefox
                            // Prevent accidental activation of menu items in Firefox (#7024 #9118)
                            if ( this.isNewMenu ) {
                                this.isNewMenu = false;
                                if ( event.originalEvent && /^mouse/.test( event.originalEvent.type ) ) {
                                    this.menu.blur();

                                    this.document.one( "mousemove", function() {
                                        $( event.target ).trigger( event.originalEvent );
                                    });

                                    return;
                                }
                            }

                            item = ui.item.data( "ui-autocomplete-item" );
                            if ( false !== this._trigger( "focus", event, { item: item } ) ) {
                                // use value to match what will end up in the input, if it was a key event
                                if ( event.originalEvent && /^key/.test( event.originalEvent.type ) ) {
                                    this._value( item.value );
                                }
                            }

                            // Announce the value in the liveRegion
                            label = ui.item.attr( "aria-label" ) || item.value;
                            if ( label && jQuery.trim( label ).length ) {
                                this.liveRegion.children().hide();
                                $( "<div>" ).text( label ).appendTo( this.liveRegion );
                            }
                        },
                        menuselect: function( event, ui ) {
                            var item = ui.item.data( "ui-autocomplete-item" ),
                                previous = this.previous;

                            // only trigger when focus was lost (click on menu)
                            if ( this.element[ 0 ] !== this.document[ 0 ].activeElement ) {
                                this.element.focus();
                                this.previous = previous;
                                // #6109 - IE triggers two focus events and the second
                                // is asynchronous, so we need to reset the previous
                                // term synchronously and asynchronously :-(
                                this._delay(function() {
                                    this.previous = previous;
                                    this.selectedItem = item;
                                });
                            }

                            if ( false !== this._trigger( "select", event, { item: item } ) ) {
                                this._value( item.value );
                            }
                            // reset the term after the select event
                            // this allows custom select handling to work properly
                            this.term = this._value();

                            this.close( event );
                            this.selectedItem = item;

                            // ANNO-TOOL
                            //
                            // The API's provided select() callback isn't
                            // called at the right time for what we need to do.
                            //
                            // Putting our handler right here is the only way
                            // to ensure that autocomplete pops up again
                            // after focusing the next point.
                            AnnotationToolHelper.labelSelected(item.value);

                            // Only focus the next point when clicking the item
                            // (not on hitting Enter to select the item,
                            // because that already goes to the next point).
                            var origEvent = event;
                            while (origEvent.originalEvent !== undefined){
                                origEvent = origEvent.originalEvent;
                            }
                            if (origEvent.type === 'click') {
                                AnnotationToolHelper.selectNextUnannotatedPoint();
                            }
                        }
                    });

                    this.liveRegion = $( "<span>", {
                        role: "status",
                        "aria-live": "assertive",
                        "aria-relevant": "additions"
                    })
                        .addClass( "ui-helper-hidden-accessible" )
                        .appendTo( this.document[ 0 ].body );

                    // turning off autocomplete prevents the browser from remembering the
                    // value when navigating through history, so we re-enable autocomplete
                    // if the page is unloaded before the widget is destroyed. #7790
                    this._on( this.window, {
                        beforeunload: function() {
                            this.element.removeAttr( "autocomplete" );
                        }
                    });
                }
            });


            // Bind autocomplete to the annotation fields.
            //
            // Note that the autocomplete bindings come AFTER our
            // hotkey bindings. This way, our hotkey bindings can
            // prevent autocomplete hotkeys from executing if they
            // want.
            //
            // TODO: Let autocomplete be an option.
            // TODO: Let machine suggestions be part of the
            // machine suggestions option. This includes the
            // modified source function, and the right arrow key
            // handler.
            $annotationField.autocomplete({
                // Auto-focus first option when menu is shown
                autoFocus: true,
                // delay in milliseconds between when a dropdown-triggering
                // event occurs and when the dropdown is actually shown.
                delay: 0,
                // Function called when a menu item is focused
                focus: function(event, ui) {
                    // Clobber jQuery UI's default behavior of
                    // auto-filling the field with the focused
                    // menu item's value.
                    //
                    // (By the way, return false really is jQuery UI's
                    // only provided way to clobber its default behavior.
                    // In other contexts, event.stopPropagation() and
                    // event.preventDefault() are better due to being
                    // more explicit.)
                    return false;
                },
                // Minimum length of field value before suggestions appear
                minLength: 0,
                // Function that gets the suggestions to show
                source: function(request, response) {

                    var suggestions = [];
                    var i;

                    if (request.term === '') {
                        // Machine suggestions for the selected points.
                        if (machineSuggestions !== null) {
                            var selectedNumbers = AnnotationToolHelper.getSelectedNumbers();
                            suggestions = getMachineSuggestions(selectedNumbers);
                        }
                        else {
                            suggestions = [];
                        }
                    }
                    else {
                        // "Labels that start with this" suggestions.
                        for (i = 0; i < labelCodes.length; i++) {
                            var codeLC = labelCodes[i].toLowerCase();
                            var termLC = request.term.toLowerCase();
                            if (codeLC.startsWith(termLC)) {
                                suggestions.push(labelCodes[i]);
                            }
                        }
                        suggestions.sort();
                    }
                    response(suggestions);
                }
            });
        }
    }
})();
