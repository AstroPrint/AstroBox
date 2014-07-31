var Utils = function() {
	return {
		timeFormat: function(seconds) {
	    	var sec_num = parseInt(seconds, 10); // don't forget the second param
	        var hours   = Math.floor(sec_num / 3600);
	        var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
	        var seconds = sec_num - (hours * 3600) - (minutes * 60);

	        if (hours   < 10) {hours   = "0"+hours;}
	        if (minutes < 10) {minutes = "0"+minutes;}
	        if (seconds < 10) {seconds = "0"+seconds;}
	        return hours+':'+minutes+':'+seconds;
	    },
	    sizeFormat: function(fileSizeInBytes) {
		   	var i = -1;
		    var byteUnits = [' kB', ' MB', ' GB', ' TB', 'PB', 'EB', 'ZB', 'YB'];
		    do {
		        fileSizeInBytes = fileSizeInBytes / 1024;
		        i++;
		    } while (fileSizeInBytes > 1024);

		    return Math.max(fileSizeInBytes, 0.1).toFixed(1) + byteUnits[i];
	    }
	}
};