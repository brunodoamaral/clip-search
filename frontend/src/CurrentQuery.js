import { writable, get } from 'svelte/store';

class VectorMean {
    constructor() {
        this.reset() ;
    }

    reset() {
        this.value = 0 ;
        this.n = 0 ;
      }

    append(newValue, w = 1.0) {
        if (this.n == 0) {
            this.n = 1 ;
            this.value = newValue ;
        } else {
            if (this.value.length != newValue.length) {
                throw new Error('New value has different len from current value') ;
            }
            
            for( let i=0; i<this.value.length; i++) {
                this.value[i] = (this.value[i] * this.n + newValue[i] * w) / (this.n + w) ;
            }

            this.n += 1 ;
        }
    }

    result(i) {
        if (this.n == 0) {
            return 0 ;
        } else {
            return this.value[i] ;
        }
    }
}
        

function createCurrentQuery() {
    const { subscribe, set, update } = writable();

    const positiveQueries = new VectorMean() ;
    const negativeQueries = new VectorMean() ;
    const imagesList = new Set() ;
    const negW = 0.8
    const imagesW = 0.75

    const resetQuery = (q) => {
        imagesList.clear();
        positiveQueries.reset();
        negativeQueries.reset();
        set(q) ;
    }

    const getImageList = () => {
        return imagesList ;
    }

    const appendQuery = async (fname, q, w) => {
        if (w > 0) {
            positiveQueries.append(q, w) ;
        } else {
            negativeQueries.append(q, -w) ;
        }

        imagesList.add(fname) ;

        let current = await get(currentQuery) ;

        for( let i=0; i<current.length; i++) {
            current[i] = current[i] * (1-imagesW) + imagesW * (positiveQueries.result(i) - negW * negativeQueries.result(i)) / (1 - negW) ;
        }

        set(current) ;
        return current ;
    }

    return {
        subscribe,
        resetQuery: resetQuery,
        appendQuery: appendQuery,
        getImageList: getImageList

    };
}

export const currentQuery = createCurrentQuery();