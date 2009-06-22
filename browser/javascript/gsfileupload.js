// GroupServer module for supporting multi-file uploads.
jQuery.noConflict();
GSFileUpload = function () {
    // Private methods
    var renameFileInputs = function(event) {
        var multiFiles = jQuery('.MultiFile-applied');
        var oldId = ''
        var newId = ''
        var i = null;
        var input = null;
        for ( i=0; i < multiFiles.length; i++ ) {
            input = jQuery(multiFiles[i]);
            oldId = input.attr('id');
            newId = oldId + '.' + i;
            input.attr('id', newId).attr('name', newId);
        }
        return true;
      };
    var addMultiFile = function () {
        var remove = '<strong><abbr title="Remove this file from the files list">X</abbr></strong>';
        var options = {
          list: '#fileList',
          STRING: {remove: remove}
        };
        jQuery('#form\\.uploadedFile').MultiFile(options);
    };

    // Public methods and properties
    return {
        init: function () {
            addMultiFile();
            jQuery('#add-to-topic').submit(renameFileInputs);
        }
    };
}(); // GSFileUpload

