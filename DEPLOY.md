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

## 3. Make shows and episodes

- **Shows** tab > **Create a show**: upload the show's directive (the show bible: title, tagline, the cast list,
  the places), a picture of each character named after them (`Barry Plum.png`) and the sets, or one zip of it all.
  The studio files the characters and sets, finds anyone already in the library, cuts everyone out and gives each
  character the stand-in voice they will keep in every episode (change it on the show's page).
- On the show's page, **Produce an episode**: upload the episode's directive or script, plus anything new (a new
  character's picture, a new set, the actors' recordings: one file per actor, named after them, or let the studio
  work out whose voice is whose). Choose **Final film** and tap **Produce**. The studio reads the scenes, the
  lines and the stage directions, casts and stages every scene, cuts the lines out of the recordings for the lip
  sync, directs, mixes and renders.
- You can lock the phone: the work carries on on the server. Open the episode again to see how far it has got
  (the **Jobs** tab shows everything), then watch the film in the app or **Download** it.
- Everything stays editable on the episode's page: sets and staging per scene (drag the characters), voices, the
  lines, stills, a quick draft, the final.

## Good to know

- The first production fetches the speech models (about 1 GB) once; it is slower than the ones after it.
- Rendering takes a few minutes for each minute of film at 1080p on the Pro Plus size.
- Your work lives on the server's disk, which survives updates and restarts. Download the finished films you want
  to keep elsewhere.
- When this repository is updated (new library characters, engine improvements), Render redeploys by itself and
  the disk keeps everything you made; new library material is added to it, nothing of yours is overwritten.
- `STUDIO_JOBS` (cores) and `FILM_MEM_GB` (memory a render may use) are set for the Pro Plus size in `render.yaml`;
  change them with the size.
