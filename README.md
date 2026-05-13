# vanam_py

**Vanam** is a system for identifying and cataloguing flora and fauna.

---

## Architecture

Vanam is split into two parts:

- **Frontend — [Vanam App](https://github.com/nuuuwan/vanam):** A React web application that allows users to upload photos and browse, search, and view plant identifications.
- **Backend — [vanam_py](https://github.com/nuuuwan/vanam_py) (this repo):** A Python service that processes uploaded photos, identifies plant species, and manages storage.

---

## How It Works

1. **Photo capture:** The user photographs a plant using their smartphone.
2. **Upload:** Using the Vanam App, the user uploads the photo to *temporary storage* — a [Vercel Blob store](https://vercel.com/nuwans-projects-4c6606c6/vanam/stores). Alongside each photo, the app also uploads a JSON metadata file containing the GPS location, timestamp, and user ID.
3. **Ingestion:** The backend (this repo) periodically checks the temporary storage and downloads both images (`data/images`) and their associated metadata (`data/image-metadata`) into permanent storage.
4. **Identification:** The backend submits each image to the [PlantNet API](https://my.plantnet.org/) — an AI-powered plant identification service — and saves the results (`data/identifications`). PlantNet analyses the visual features of a plant photo and returns a ranked list of likely species matches.
5. **Display:** The identified plants and their images are made available to the frontend app for browsing and searching.
6. **Cleanup:** The backend periodically purges processed images from the Vercel temporary storage.

---

## Name

The name *vanam* comes from Sanskrit, meaning "forest", and is also the root of the Sinhala word *vanaya* (වනය) and the Tamil word vanam (வனம்), both meaning forest.
