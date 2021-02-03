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
            this.n = w ;
            this.value = [] ;
            for( let i=0; i<newValue.length; i++) {
                this.value.push(newValue[i] / w) ;
            }
        } else {
            if (this.value.length != newValue.length) {
                throw new Error('New value has different len from current value') ;
            }
            
            for( let i=0; i<this.value.length; i++) {
                this.value[i] = (this.value[i] * this.n + newValue[i] * w) / (this.n + w) ;
            }

            this.n += w ;
        }
    }

    result() {
        return [...this.value] ;
    }
}
        

function createCurrentQuery() {
    const { subscribe, set, update } = writable();

    const queryList = new VectorMean() ;
    const imagesList = new Set() ;
    const negW = 0.8 ;
    const posW = 1 ;
    const oriW = 2 ;

    const resetQuery = (q) => {
        imagesList.clear();
        queryList.reset();

        queryList.append(q, oriW) ;

        set(queryList.result()) ;
    }

    const getImageList = () => {
        return imagesList ;
    }

    const appendQuery = async (fname, q, w) => {
        if (w > 0) {
            queryList.append(q, posW * w) ;
        } else {
            queryList.append(q, negW * w) ;
        }

        imagesList.add(fname) ;

        set(queryList.result()) ;
    }

    return {
        subscribe,
        resetQuery: resetQuery,
        appendQuery: appendQuery,
        getImageList: getImageList

    };
}

export const currentQuery = createCurrentQuery();