class CPCBatchEditor {

    constructor() {
        this.fileDropZone.addEventListener('dragover', e => {
            // Prevent navigation.
            e.preventDefault();
        });
        this.fileDropZone.addEventListener('drop', this.onFilesDrop.bind(this));

        this.form.onsubmit = this.submitFiles.bind(this);
    }

    get fileDropZone() {
        return document.getElementById('file-drop-zone');
    }
    get filePreview() {
        return document.getElementById('file-preview');
    }
    get form() {
        return document.getElementById('form');
    }
    get submitButton() {
        return this.form.querySelector('input[type="submit"]');
    }
    get downloadForm() {
        return document.getElementById('download-form');
    }

    async onFilesDrop(event) {
        // Prevent navigation.
        event.preventDefault();

        let reader = new DataTransferReader(
            {acceptedExtensions: ['cpc']}
        );
        this.files = await reader.getFiles(event.dataTransfer.items);

        this.filePreview.textContent =
            `Detected ${this.files.length} .cpc file(s).`;

        this.submitButton.disabled = this.files.length === 0;
    }

    async submitFiles(event) {
        // Don't let the form do a non-Ajax submit
        // (browsers' default submit behavior).
        event.preventDefault();

        this.submitButton.disabled = true;

        // Create a zip of the selected CPC files.
        let zipFile = await this.createZip();

        let formData = new FormData(this.form);
        formData.append('cpc_zip', zipFile);

        util.fetch(
            this.form.action,
            {method: 'POST', body: formData},
            (response) => {
                // Submit the download form, passing in the session key
                // from the POST response.
                // The download response will contain the edited .cpc files.
                let sessionKeyField = this.downloadForm.querySelector(
                    'input[name="session_key"]');
                sessionKeyField.value = response.session_key;
                this.downloadForm.submit();
            }
        );
    }

    async createZip() {
        // zip is from zipjs module (@zip.js/zip.js on npm).
        const blobWriter = new zip.BlobWriter("application/zip");
        const writer = new zip.ZipWriter(blobWriter);

        for (let file of this.files) {
            await writer.add(file.filepath, new zip.BlobReader(file));
        }
        await writer.close();

        // Return the zip file as a Blob
        return blobWriter.getData();
    }
}


/*
Adapted from:
https://github.com/anatol-grabowski/datatransfer-files-promise
 */
class DataTransferReader {

    constructor({acceptedExtensions = null} = {}) {
        this.acceptedExtensions = acceptedExtensions;
        this.totalFilesRead = 0;
        this.warnedAboutFileCount = false;
    }

    isFileAccepted(file) {
        if (!this.acceptedExtensions) {
            // All extensions are accepted.
            return true;
        }
        let extension = file.name.split('.').pop().toLowerCase();
        return this.acceptedExtensions.includes(extension);
    }

    incrementFilesReadCount() {
        if (this.warnedAboutFileCount) {
            return;
        }

        this.totalFilesRead++;
        if (this.totalFilesRead > 5000) {
            let keepGoing = window.confirm("You've dragged in a lot of files (over 5000, including non-cpc). Is this what you wanted to do? Select OK to keep scanning, or select Cancel to abort.");
            this.warnedAboutFileCount = true;

            if (!keepGoing) {
                // TODO: Where to catch this?
                throw new Error("Aborted after high file count check.");
            }
        }
    }

    readFile(entry, path = '') {
        return new Promise((resolve, reject) => {
            entry.file(file => {
                // Save full path
                file.filepath = path + file.name;
                resolve(file);
            }, (err) => {
                checkErr(err);  // TODO
                reject(err);
            })
        })
    }

    dirReadEntries(dirReader, path) {
        return new Promise((resolve, reject) => {
            dirReader.readEntries(async entries => {
                let files = [];
                for (let entry of entries) {
                    const itemFiles = await this.getFilesFromEntry(entry, path);
                    files = files.concat(itemFiles);
                }
                resolve(files);
            }, (err) => {
                checkErr(err);
                reject(err);
            })
        })
    }

    async readDir(entry, path) {
        const dirReader = entry.createReader();
        const newPath = path + entry.name + '/';
        let files = [];
        let newFiles;

        // Each readEntries call only returns up to 100 entries in a
        // directory (at least in Chrome). Must call readEntries repeatedly
        // until it returns an empty array.
        do {
            newFiles = await this.dirReadEntries(dirReader, newPath);
            files = files.concat(newFiles);
        } while (newFiles.length > 0);

        return files;
    }

    async getFilesFromEntry(entry, path = '') {
        if (entry.isFile) {
            const file = await this.readFile(entry, path);
            this.incrementFilesReadCount();
            if (this.isFileAccepted(file)) {
                return [file];
            }
            else {
                return [];
            }
        }
        if (entry.isDirectory) {
            const files = await this.readDir(entry, path);
            return files;
        }
        // throw new Error('Entry not isFile and not isDirectory - unable to get files')
    }

    async getFiles(dataTransferItems) {
        let files = [];
        let entries = [];

        // Pull out all entries before reading them
        for (let i = 0, ii = dataTransferItems.length; i < ii; i++) {
            entries.push(dataTransferItems[i].webkitGetAsEntry());
        }

        // Recursively read through all entries
        for (let entry of entries) {
            const newFiles = await this.getFilesFromEntry(entry);
            files = files.concat(newFiles);
        }

        return files;
    }
}
