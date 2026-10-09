import Papa from 'papaparse';
import readXlsxFile from 'read-excel-file/browser';
import {expressionBuilder,metadataIds} from './expression.js';
export async function readExpression(file,table,onProgress=()=>{}) {
  metadataIds(table);
  if(file.size>100*1024*1024)throw Error('Expression files must be smaller than 100 MB. Export a subset first.');
  const parser=expressionBuilder(file.name);
  if(/\.xlsx$/i.test(file.name)) {
    if(file.size>15*1024*1024)throw Error('For workbooks larger than 15 MB, export the expression sheet as CSV or TSV.');
    const rows=await readXlsxFile(file);rows.forEach(row=>parser.add(row));return parser.finish(table);
  }
  if(!/\.(csv|tsv|txt)$/i.test(file.name))throw Error('Upload a CSV, TSV, TXT or XLSX expression matrix (genes in rows, cells in columns).');
  return new Promise((resolve,reject)=>{
    let failed=false;
    Papa.parse(file,{header:false,skipEmptyLines:'greedy',delimiter:/\.tsv$/i.test(file.name)?'\t':'',worker:true,chunkSize:1024*1024,
      chunk(result,reader){if(failed)return;try{if(result.errors.length)throw Error('Could not parse expression matrix: '+result.errors[0].message);for(const row of result.data)parser.add(row);onProgress(result.meta.cursor);}catch(error){failed=true;reader.abort();reject(error);}},
      complete(){if(failed)return;try{resolve(parser.finish(table));}catch(error){reject(error);}},error(error){failed=true;reject(error);}
    });
  });
}
