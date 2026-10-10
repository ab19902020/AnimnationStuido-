# Running the studio as a phone app

The studio's engine (cutting out characters, lip sync, rendering) is too heavy for a phone, so it runs on a
server in the cloud, and your phone opens it as an app: an icon on the home screen, full screen, password
protected. Everything is done from the phone; no PC is needed at any point.

## 1. Put the studio on a server (once, about 15 minutes)

The repository comes ready for [Render](https://render.com) (`render.yaml`). On your phone's browser:

1. Go to **render.com**, sign up with **GitHub** (the account that has this repository) and add a payment card.
   The studio needs the **Pro Plus** size (8 GB of memory, 4 CPUs) and a 50 GB disk: rendering a film takes the
   memory, and the disk holds the library, your shows and finished films. Check Render's pricing page for the
   current monthly cost before you start.
2. Tap **New** > **Blueprint**, pick this repository (`animnationstuido-`) and the branch to run (the one with
   this file in it, normally `main` once the studio branch is merged).
3. Render asks for **STUDIO_PASSWORD**: choose the password the app will open with. Tap **Apply**.
4. The first build takes about 10 minutes. When it says **Live**, tap the address at the top
   (`https://animation-studio-....onrender.com`).

Any other host that runs a Docker image with a persistent disk works too (the `Dockerfile`):

```bash
docker build -t animation-studio .
docker run -d -p 8000:8000 -v studio-data:/data -e STUDIO_PASSWORD='choose one' animation-studio
```

## 2. Install it on your phone

Open the address, enter the password, then:

- **iPhone (Safari):** the Share button > **Add to Home Screen**.
- **Android (Chrome):** the ⋮ menu > **Install app** (or **Add to Home screen**).

From then on the **Studio** icon opens it full screen, like any app, and it stays logged in.

## 3. Make a production

The **Produce** tab (the app opens on it) is the three steps:

1. **New cast members**: pick the pictures of anyone new in this production, one per character, named after them
   (`Carlos Baleba.png`: the name is read from the file name and can be corrected before adding). Each is cut out
   and checked; the **Cast** tab shows them, and **Fix face** sets the eyes and mouth if a face isn't found.
2. **New backgrounds**: pick the new sets, named for the place (`Carrick's kitchen.png`).
3. **Produce it**: pick the director's zip and the production notes, as they came, choose **Final film** and tap
   **Produce**. The studio finds the script among the documents, casts every speaker from the cast library (the
   full names in the notes tell people with the same first name apart), gives each scene the set its heading
   names (or, failing that, the set the notes describe for it, or the newest one), gives each recording to whoever
   it is named for or whoever's lines it hears (anyone without one gets a stand-in voice), stages the scenes, cuts
   out the characters, syncs the lips, directs, mixes and renders.

If the script has someone the cast library doesn't, the episode's page says who, with an **Add their picture**
button for each and **Produce again**. You can lock the phone while it works: the **Jobs** tab and the episode's
page show how far it has got; then watch the film in the app or **Download** it. Everything stays editable on the
episode's page (sets and staging per scene, voices, lines, stills, a quick draft, the final).

A series can also be kept as a **Show** (Episodes > Shows): its cast, sets and stand-in voices are kept and every
episode produced in it reuses them.

## Good to know

- The first production fetches the speech models (about 1 GB) once; it is slower than the ones after it.
- Rendering takes a few minutes for each minute of film at 1080p on the Pro Plus size.
- Your work lives on the server's disk, which survives updates and restarts. Download the finished films you want
  to keep elsewhere.
- When this repository is updated (new library characters, engine improvements), Render redeploys by itself and
  the disk keeps everything you made; new library material is added to it, nothing of yours is overwritten.
- `STUDIO_JOBS` (cores) and `FILM_MEM_GB` (memory a render may use) are set for the Pro Plus size in `render.yaml`;
  change them with the size.
