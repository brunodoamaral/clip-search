<script>
    import Dropzone from "svelte-file-dropzone";
    import { currentQuery } from './CurrentQuery.js';
    import { fade } from 'svelte/transition';

    let draggingVisible = false ;
    let prompt = "" ;
    let lastPrompt = "" ;
    let results = [] ;
    let currentPromisse = Promise.all([]) ;
    let currentImages = [] ;

    async function doFetchJSON(url, params={}) {
        return fetch(url, params).then(
            r => r.json()
        ) ;
    }

    function resetSearch() {
        prompt = "" ;
        currentImages = [] ;
    }

    function loadImage(selectedFile) {
        var reader = new FileReader();

        reader.onload = function(event) {
            let imgObject = new Object() ;
            imgObject.src = event.target.result;
            currentImages = [...currentImages, imgObject] ;
        };

        reader.readAsDataURL(selectedFile);
    }

    const handleFilesSelect = async(e) => {
        const { acceptedFiles } = e.detail;
        let data = new FormData();
        currentImages = [] ;
        for (let i = 0; i < acceptedFiles.length; i++) {
            data.append("fileToUpload[]", acceptedFiles[i]);

            loadImage   (acceptedFiles[i]) ;
        }
        currentPromisse = doFetchJSON('/get-embedding', {
            method: 'POST',
            body: data,
        }).then(json => {
            prompt = "" ;
            lastPrompt = "" ;
            draggingVisible = false ;
            let query = json["_mean_"] ;
            return newSearch(query) ;
        })
    }

    const getImageEmbeddings = async (fname) => {
        var url = new URL("/get-embedding", document.location);
        url.searchParams.append("src_image", fname);

        return doFetchJSON(url) ;
    }

    const newSearch = async (query) => {
        currentQuery.resetQuery(query) ;

        let data = {
            'query': $currentQuery
        }

        results = await doFetchJSON('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
    }

    const searchByPrompt = async (e) => {
        var url = new URL("/get-embedding", document.location);
        currentImages = [] ;
        url.searchParams.append("prompt", prompt);
        lastPrompt = prompt ;

        currentPromisse = doFetchJSON(url).then(query => newSearch(query)) ;
    }

    const handleKeyup = (event) => {
		if (event.code == 'Enter' || event.code == 'NumpadEnter') {
			event.preventDefault();
            return searchByPrompt(event) ;
        }
    }

    const dragenterHeader = (e) => {
        draggingVisible = true ;
    }

    const dragleaveHeader = (e) => {
        draggingVisible = false ;
    }

    const appendQuery = async (result, w) => {
        let embedding = await getImageEmbeddings(result.fname) ;

        currentQuery.appendQuery(result.fname, embedding, w) ;

        let data = {
            'query': $currentQuery,
            'query_excludes': Array.from(currentQuery.getImageList())
        }

        results = await doFetchJSON('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
    }


</script>

<style>
    :global(body) {
        background-color: rgb(0, 164, 205);
        color: white ;
    }

    h1 {
        margin: 4px auto;
    }

    .header {
        height: 120px ;
        display: grid;
        grid-template-columns: 0.25fr auto 0.25fr;
        margin: 5px ;
    }

    .positives {
        /* background-color: mediumseagreen; */
    }

    .negatives {
        /* background-color: pink ; */
    }

    .search-area {
        text-align: center;
    }

    .search-box {
        width: 50% ;
        height: 50px ;
        margin: auto;
    }

    .search-query {
        display: grid ;
        height: 50px;
        margin: 5px 0px;
    }

    .search-images {
        width: 30px ;
        height: 30px ;
        vertical-align: middle;
        margin: 0px 5px;
    }

    .results {
		width: 100%;
		display: grid;
		grid-template-columns: repeat( auto-fit, minmax(250px, 1fr) );
		grid-gap: 8px;
    }

    .result {
        text-align: center;
        background-color: rgba(255, 255, 255, 0.20);
        padding: 5px;
        position: relative;
        height: 260px;
    }

    .result button {
        font-size: 10px;
    }

    .results img {
        max-width: 80%;
        max-height: 200px;
        margin: 10px auto;
        display: block;
        border: 1px solid white;
        position: absolute;
        margin: auto;
        top: 0;
        bottom: 0;
        left: 0;
        right: 0;
    }

    .btn-search {
        width: 110px ;
    }
</style>

<div class="content">
    <div class="header">
        <div class="positives">
        </div>
        <div class="search-area" on:dragenter|preventDefault={dragenterHeader} on:dragleave={dragleaveHeader}>
            {#if draggingVisible}
                <Dropzone
                    on:dropaccepted={handleFilesSelect}
                    accept="image/*"
                    multiple={true}
                />
            {:else}
                <h1>CLIP-Search</h1>

                <input placeholder="Type a text or drag images here" bind:value={prompt} class="search-box" on:keyup={handleKeyup}/>
                {#await currentPromisse}
                    <button class="btn-search" disabled="disabled">Searching...</button>
                {:then}
                    <button class="btn-search" disabled={prompt.length == 0} on:click={searchByPrompt}>Search</button>
                {/await}

            {/if}
        </div>
        <div class="negatives">
            
        </div>
    </div>
    <div class="search-query">
        {#if results.length > 0}
            <p>
            Search results for:
            {#if currentImages.length > 0}
                {#each currentImages as image}
                <img src={image.src} alt="search image" class="search-images"/>
                {/each}
            {:else}
                {lastPrompt}
            {/if}
            </p>
        {/if}
    </div>
    <div class="results">
        {#each results as result (result.fname)}
            <div class="result" transition:fade|local>
                <button on:click={appendQuery(result, 1)}>More like this</button>
                <button on:click={appendQuery(result, -1)}>Less like this</button>
                <a href={result.fname} target='_blank'>
                    <img src={result.thumb} alt={result.thumb}/>
                </a>
            </div>
        {/each}
    </div>
</div>
