# Putting British Voice on the Microsoft Store

You do the account steps; GitHub builds the Store file for you automatically.

## 1. Create your free Microsoft developer account (start today)
1. Go to **https://storedeveloper.microsoft.com** and choose **Individual developer**.
2. Sign in with your Microsoft account, fill in your details, verify your ID.
3. Approval can take a few days. You'll get an email when it's ready.

## 2. Reserve the app name
1. Open **https://partner.microsoft.com/dashboard/apps-and-games/overview**.
2. **+ New product** → **MSIX or PWA app** → type **British Voice** → **Reserve product name**.
   (If taken: "British Voice for Calls".)
3. Open the app → **Product management** → **Product identity**. Copy these 3 values:
   - **Package/Identity/Name**
   - **Package/Identity/Publisher** (starts with `CN=`)
   - **Package/Properties/PublisherDisplayName**

## 3. Put the code on GitHub (free)
1. Sign up at **https://github.com** if you don't have an account.
2. Create a new repository called **british-voice**, set it to **Public** (required by the
   open-source licence of the voice engine), and upload the files from this folder
   (including the `.github` folder).
3. In the repository: **Settings → Secrets and variables → Actions → Variables tab →
   New repository variable**. Add:
   - `IDENTITY_NAME` = Package/Identity/Name
   - `PUBLISHER` = Package/Identity/Publisher
   - `PUBLISHER_DISPLAY_NAME` = Package/Properties/PublisherDisplayName
   - `DISPLAY_NAME` = the name you reserved (e.g. British Voice)

## 4. Build the Store file
1. In the repository: **Actions → Build Windows app → Run workflow**.
2. Wait about 10 minutes for the green tick.
3. Open the run → under **Artifacts** download **BritishVoice-Store-package** and unzip it.
   You now have **BritishVoice-1.0.X.0.msix**.

## 5. Submit to the Store
In Partner Center open the app → **Start submission**:
- **Pricing and availability**: Free. Under *Visibility* choose
  **"Hide this product in the Store"** (only people with the link can install it), or Public.
- **Properties**: Category **Productivity**. Privacy policy URL: the link to `PRIVACY.md`
  in your GitHub repository (first replace `YOUR-EMAIL-HERE` in that file with your email).
- **Age ratings**: answer the questionnaire (no violence, no data collection, no purchases).
- **Packages**: upload the `.msix` file.
- **Store listings → English**: copy everything from `packaging/store/LISTING.md`;
  screenshot = `packaging/store/screenshot.png`; logo = `packaging/store/StoreListing300.png`.
- **Submission options → Restricted capabilities**: paste the *runFullTrust justification*
  from `LISTING.md`.
- **Submission options → Notes for certification**: paste the certification notes from `LISTING.md`.
- Click **Submit to the Store**. Review usually takes 1–3 business days.

## 6. Install it (you and your team)
1. Open the Store link from Partner Center (*Product management → Store link*) → **Get**.
2. Open **British Voice** → click **Get virtual microphone (free)** → install VB-Cable
   (right-click `VBCABLE_Setup_x64` → Run as administrator → Install Driver) → restart PC.
3. Open British Voice → pick a voice → **Start**.
4. Zoom/Teams → Microphone → **CABLE Output**. Use headphones.

## Updating the app later
Change the code on GitHub → the build runs automatically → in Partner Center click
**Update** on the app, upload the new `.msix`, submit.
