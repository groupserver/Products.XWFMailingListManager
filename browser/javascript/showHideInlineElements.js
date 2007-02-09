function showHideInline(remainderId, discloseButtonId) 
{
    //const hiddenArrow = "\u25b6";
    //const shownArrow = "\u25bc"
    var discloseElement = document.getElementById(discloseButtonId);

    if (discloseElement.getAttribute('class') == 'shownArrow')
    { 
        discloseElement.setAttribute('title', "Show the footer");
        discloseElement.setAttribute('class', "hiddenArrow");

    }
    else
    {
        discloseElement.setAttribute('title', "Hide the footer");
        discloseElement.setAttribute('class', "shownArrow");
    }
    Effect.toggle(remainderId,'blind', {duration: 2, delay: 0});
}
