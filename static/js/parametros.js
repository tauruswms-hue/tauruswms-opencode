$(document).ready(function() {
    $('.dropdown-toggle').on('click', function(e) {
        e.preventDefault();
        $(this).closest('.params-nav-dropdown').toggleClass('open');
    });
});