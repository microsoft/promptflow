// Get the head element
let head = document.getElementsByTagName("head")[0];

// Create the script element
let script = document.createElement("script");
script.async = true;
script.src = "https://www.googletagmanager.com/gtag/js?id=G-KZXK5PFBZY";

// Create another script element for the gtag code
let script2 = document.createElement("script");
script2.innerHTML = ` window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('js', new Date());gtag('config', 'G-KZXK5PFBZY'); `;

// Insert the script elements after the head element
head.insertAdjacentElement("afterbegin", script2);
head.insertAdjacentElement("afterbegin", script);

// This is used to zoom in images when clicked on
window.onload = () => {
    if (document.getElementById("lightbox") === null){
      // Append lightbox div to each page
      let div = document.createElement('div');
      div.innerHTML = '<div id="lightbox"></div>';
      document.body.appendChild(div);
    }

    // (A) GET LIGHTBOX & ALL .ZOOMD IMAGES
    let all = document.getElementsByClassName("bd-article")[0].getElementsByTagName("img"),
        lightbox = document.getElementById("lightbox");

    // (B) CLICK TO SHOW IMAGE IN LIGHTBOX
    // * SIMPLY CLONE INTO LIGHTBOX & SHOW
    if (all.length>0) { for (let i of all) {
        // skip if class contains avatar or img_ev3q(Open on github button)
         if (i.classList.contains("avatar") || i.classList.contains("img_ev3q")) {
              continue;
         }
      i.onclick = () => {
        let clone = i.cloneNode();
        clone.className = "";
        lightbox.innerHTML = "";
        lightbox.appendChild(clone);
        lightbox.className = "show";
      };
    }}

    // (C) CLICK TO CLOSE LIGHTBOX
    lightbox.onclick = () => {
      lightbox.className = "";
    };
};

if (window.location.pathname === "/promptflow/" || window.location.pathname === "/promptflow/index.html") {
  // This is used to control homepage background
  let observer = new MutationObserver(function(mutations) {
    const dark = document.documentElement.dataset.theme == 'dark';
    document.body.style.backgroundSize = "100%";
    document.body.style.backgroundPositionY = "bottom";
    document.body.style.backgroundRepeat = "no-repeat"
  })
  observer.observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
}
