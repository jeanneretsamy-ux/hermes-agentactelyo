import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import {createHash} from 'node:crypto'
import {DatabaseSync} from 'node:sqlite'

// This runs against the actual installed EXE and its isolated, synthetic profile.
export async function verifyFinance(page,proof,fixture){
  assert.equal(createHash('sha256').update(fs.readFileSync(fixture)).digest('hex'),'a921ec77f8ee7d5484d88c6304fca5a80093f3c2cea40d9ba38818e5c5480f9b','The committed binary PDF fixture must survive checkout byte for byte.')
  await page.getByRole('button',{name:'Pilotage financier',exact:true}).click()
  await page.getByRole('button',{name:'Actualiser le registre réel',exact:true}).click()
  const dossier=page.getByLabel('Dossier',{exact:true})
  const option=dossier.locator('option').filter({hasText:'Dossier QA échéances'})
  await option.waitFor({state:'attached',timeout:60000})
  assert.equal(await option.count(),1,'A unique synthetic dossier must be selected.')
  await dossier.selectOption(await option.getAttribute('value'))
  const finance=page.getByRole('region',{name:'Pilotage financier du cabinet',exact:true})
  const details=title=>finance.locator('details').filter({has:page.locator('summary',{hasText:title})}).last()
  const confirm=async()=>{
    const button=finance.getByRole('button',{name:'Confirmer l’enregistrement',exact:true})
    await button.click();await button.waitFor({state:'hidden',timeout:60000})
    await finance.getByText(/Écriture enregistrée et registre relu/).waitFor({timeout:60000})
  }
  const fees=details('Saisir une diligence ou une dépense');await fees.locator('summary').click()
  await fees.getByLabel('Libellé',{exact:true}).fill('Diligence QA installateur finance')
  await fees.getByLabel('Taux facturable (€/heure)',{exact:true}).fill('125')
  await fees.getByLabel('Durée (minutes)',{exact:true}).fill('60')
  await fees.getByLabel('Taux de taxe (%) défini par le cabinet',{exact:true}).fill('0')
  await fees.getByRole('button',{name:'Préparer la diligence à valider',exact:true}).click();await confirm()
  const review=details('Contrôler les diligences en attente');await review.locator('summary').click()
  await review.getByRole('button',{name:'Préparer la validation',exact:true}).click();await confirm()
  const orders=details('Bons à facturer numérotés');await orders.locator('summary').click()
  await orders.getByLabel('Diligence QA installateur finance',{exact:false}).check()
  await orders.getByRole('button',{name:'Préparer le bon à facturer',exact:true}).click();await confirm()
  const docs=details('Documents financiers et pièces PDF');await docs.locator('summary').click()
  await docs.getByLabel('Document PDF',{exact:true}).setInputFiles(fixture)
  await docs.getByRole('button',{name:'Déposer le document et vérifier son empreinte',exact:true}).click()
  await docs.getByText('Document déposé et empreinte vérifiée.',{exact:true}).waitFor({timeout:120000})
  const original=docs.getByRole('article',{name:path.basename(fixture),exact:true})
  await original.getByRole('button',{name:'Lire le scan par OCR local',exact:true}).click()
  const extracted=docs.getByRole('region',{name:'Texte extrait du document',exact:true})
  await extracted.waitFor({timeout:150000})
  const text=await extracted.getByRole('textbox').inputValue()
  assert.match(text,/1234/);assert.match(text,/250/);assert.match(text,/ACTELYO/i)
  await docs.getByLabel('Numéro de pièce pour le tampon',{exact:true}).fill('7')
  await original.getByRole('button',{name:'Préparer la copie tamponnée',exact:true}).click();await confirm()
  const database=new DatabaseSync(path.join(proof,'clean-home','projects.db'),{readOnly:true})
  let source,receipt,copy,order
  try{
    source=database.prepare('SELECT id,sha256,extraction_mode,extraction_source_id FROM legal_finance_files WHERE filename=? AND source_file_id IS NULL').get(path.basename(fixture))
    assert(source);assert.equal(source.sha256,createHash('sha256').update(fs.readFileSync(fixture)).digest('hex'))
    receipt=database.prepare('SELECT id,kind,source_file_id FROM legal_finance_files WHERE id=?').get(source.extraction_source_id)
    assert.equal(receipt.kind,'ocr_result');assert.equal(receipt.source_file_id,source.id)
    copy=database.prepare('SELECT id,sha256,piece_number FROM legal_finance_files WHERE source_file_id=? AND piece_number=7').get(source.id)
    assert(copy);assert.notEqual(copy.sha256,source.sha256)
    order=database.prepare("SELECT reference,status,net_cents FROM legal_billing_orders WHERE status='ready'").get()
    assert(order);assert.equal(order.net_cents,12500)
  }finally{database.close()}
  await extracted.scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(proof,'installed-finance.png'),timeout:60000})
  fs.writeFileSync(path.join(proof,'installed-finance.json'),JSON.stringify({passed:true,scope:'Actual installed EXE; synthetic fees approved, numbered BAF, immutable PDF upload, local French OCR, stamped copy, native SQLite readback. No fiscal issuance or external actions.',order,source,receipt,copy,text},null,2))
}
