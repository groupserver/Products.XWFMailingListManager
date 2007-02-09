function showHideInline(remainderId, discloseButtonId) 
{
    var i=0;
    var remainderElement = document.getElementById(remainderId);
    var discloseElement = document.getElementById(discloseButtonId);
    const hiddenArrow = "\u25b6";
    const shownArrow = "\u25bc"
    
    if (discloseElement.getAttribute('class') == 'shownArrow')
    { 
        //remainderElement.setAttribute('class', 'emailRemainderHidden');
        discloseElement.setAttribute('title', "Show the footer");
        discloseElement.setAttribute('class', "hiddenArrow");

    }
    else
    {
        //remainderElement.setAttribute('class', 'emailRemainderShown');
        discloseElement.setAttribute('title', "Hide the footer");
        discloseElement.setAttribute('class', "shownArrow");
    }
    Effect.toggle(remainderId,'blind', {duration: 2, delay: 0});
}
