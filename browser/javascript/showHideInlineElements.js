function showHideInline(remainderId, discloseButtonId) 
{
    var i=0;
    var remainderElement = document.getElementById(remainderId);
    var discloseElement = document.getElementById(discloseButtonId);
    
    const hiddenArrow = "\u25b6";
    const shownArrow = "\u25bc"
    
    if (remainderElement.getAttribute('class') == 'emailRemainderShown')
    { 
        remainderElement.setAttribute('class', 'emailRemainderHidden');
        discloseElement.setAttribute('title', 
                                      "Show the email footer");
        discloseElement.replaceChild(document.createTextNode(hiddenArrow),
                                     discloseElement.childNodes[0]);
    }
    else
    {
        remainderElement.setAttribute('class', 'emailRemainderShown');
        discloseElement.setAttribute('title', 
                                      "Hide the email footer");
        discloseElement.replaceChild(document.createTextNode(shownArrow),
                                     discloseElement.childNodes[0]);
    }
}
