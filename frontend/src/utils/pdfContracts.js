// CIUDAD. — Generador de PDFs legales por tipo de contrato.
// Tres plantillas: Alquiler Vivienda (Ley 27.551 / DNU 70/2023),
// Alquiler Comercial (CCyC arts. 1187-1226), Boleto de Compraventa (CCyC arts. 1170-1185).
import { jsPDF } from 'jspdf'

const W = 210
const H = 297
const M = 22
const COL_BG_DARK   = [10, 10, 10]
const COL_BG_LIGHT  = [247, 247, 247]
const COL_TEXT      = [10, 10, 10]
const COL_MUTED     = [115, 115, 115]
const COL_SOFT      = [200, 200, 200]
const COL_WHITE     = [255, 255, 255]

// ---------- helpers ----------

function nuevoDocumento() {
  return new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
}

function header(doc, titulo, subtitulo, codigo) {
  doc.setFillColor(...COL_BG_DARK)
  doc.rect(0, 0, W, 32, 'F')
  doc.setTextColor(...COL_WHITE)
  doc.setFontSize(20)
  doc.setFont('helvetica', 'bold')
  doc.text('CIUDAD.', M, 14)
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.text('Inmuebles - Contratos - Gestion', M, 20)
  doc.setFontSize(10)
  doc.setFont('helvetica', 'bold')
  doc.text(codigo || '', W - M, 14, { align: 'right' })
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.text(subtitulo || '', W - M, 20, { align: 'right' })

  doc.setTextColor(...COL_TEXT)
  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.text(titulo, W / 2, 44, { align: 'center' })
}

function footer(doc, codigo) {
  const pages = doc.internal.getNumberOfPages()
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i)
    doc.setDrawColor(...COL_SOFT)
    doc.setLineWidth(0.2)
    doc.line(M, H - 14, W - M, H - 14)
    doc.setFontSize(7)
    doc.setTextColor(...COL_MUTED)
    doc.setFont('helvetica', 'normal')
    doc.text(`CIUDAD. - Generado el ${new Date().toLocaleDateString('es-AR')}`, M, H - 9)
    doc.text(`${codigo || ''}  -  Pagina ${i} de ${pages}`, W - M, H - 9, { align: 'right' })
  }
}

function ensureSpace(doc, y, needed = 20) {
  if (y + needed > H - 20) {
    doc.addPage()
    return 24
  }
  return y
}

function clausulaTitulo(doc, y, numero, titulo) {
  y = ensureSpace(doc, y, 12)
  doc.setFillColor(...COL_BG_LIGHT)
  doc.rect(M, y, W - M * 2, 7, 'F')
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  doc.setTextColor(...COL_TEXT)
  doc.text(`${numero}. ${titulo.toUpperCase()}`, M + 3, y + 4.8)
  return y + 11
}

function parrafo(doc, y, texto) {
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  doc.setTextColor(...COL_TEXT)
  const lines = doc.splitTextToSize(texto, W - M * 2)
  for (const line of lines) {
    y = ensureSpace(doc, y, 6)
    doc.text(line, M, y)
    y += 5
  }
  return y + 2
}

function dato(doc, y, label, valor) {
  y = ensureSpace(doc, y, 6)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(...COL_MUTED)
  doc.text(label, M, y)
  doc.setTextColor(...COL_TEXT)
  doc.setFont('helvetica', 'bold')
  doc.text(String(valor || '—'), M + 60, y)
  return y + 6
}

function firmas(doc, etiquetaIzq, etiquetaDer) {
  let y = H - 50
  doc.setDrawColor(...COL_SOFT)
  doc.setLineWidth(0.4)
  doc.line(M, y, M + 70, y)
  doc.line(W - M - 70, y, W - M, y)
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(...COL_MUTED)
  doc.text(etiquetaIzq, M + 35, y + 5, { align: 'center' })
  doc.text(etiquetaDer, W - M - 35, y + 5, { align: 'center' })
  doc.text('Firma y aclaracion', M + 35, y + 10, { align: 'center' })
  doc.text('Firma y aclaracion', W - M - 35, y + 10, { align: 'center' })
}

function fmtMoneda(n) {
  if (n == null || n === '' || isNaN(Number(n))) return '—'
  return `$${Number(n).toLocaleString('es-AR')}`
}

function fmtFecha(s) {
  if (!s) return '—'
  try {
    const d = new Date(s + 'T00:00:00')
    return d.toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })
  } catch {
    return s
  }
}

function clienteCompleto(c) {
  if (!c) return { nombre: 'Sin asignar', dni: '', tel: '', email: '' }
  const nombre = c.razon_social || `${c.nombre || ''} ${c.apellido || ''}`.trim() || 'Sin asignar'
  return {
    nombre,
    dni: c.documento || '',
    tel: c.telefono || '',
    email: c.email || '',
  }
}

function bloqueParte(doc, y, etiqueta, parte) {
  y = ensureSpace(doc, y, 28)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  doc.setTextColor(...COL_MUTED)
  doc.text(etiqueta.toUpperCase(), M, y)
  y += 6
  y = dato(doc, y, 'Nombre / Razon social', parte.nombre)
  if (parte.dni)   y = dato(doc, y, 'DNI / CUIT',           parte.dni)
  if (parte.tel)   y = dato(doc, y, 'Telefono',             parte.tel)
  if (parte.email) y = dato(doc, y, 'Email',                parte.email)
  return y + 3
}

// ---------- TEMPLATE: ALQUILER VIVIENDA (Ley 27.551 / DNU 70/2023) ----------

function pdfAlquilerVivienda({ contrato, propiedad, propietario, inquilino }) {
  const doc = nuevoDocumento()
  const codigo = contrato.codigo || `ALQ-${contrato.id}`
  header(doc, 'CONTRATO DE LOCACION DE VIVIENDA', 'Locacion urbana', codigo)

  let y = 54
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  doc.setTextColor(...COL_TEXT)
  const intro = `En la Ciudad de Buenos Aires, a los ${fmtFecha(contrato.fecha_inicio)}, entre las partes que a continuacion se identifican, se celebra el presente CONTRATO DE LOCACION DE INMUEBLE CON DESTINO A VIVIENDA UNICA Y DE USO FAMILIAR, sujeto a las disposiciones del Codigo Civil y Comercial de la Nacion (arts. 1187 a 1226) y la Ley 27.551 de Locaciones Urbanas con las modificaciones del DNU 70/2023, conforme a las siguientes clausulas:`
  y = parrafo(doc, y, intro)

  y = bloqueParte(doc, y, 'LOCADOR (propietario)', clienteCompleto(propietario))
  y = bloqueParte(doc, y, 'LOCATARIO (inquilino)', clienteCompleto(inquilino))

  y = clausulaTitulo(doc, y, 'PRIMERA', 'Objeto')
  y = parrafo(doc, y, `EL LOCADOR da en locacion al LOCATARIO, quien acepta de conformidad, el inmueble ubicado en ${propiedad?.direccion || 'sin especificar'}, ${propiedad?.ciudad || ''}, ${propiedad?.provincia || ''}. El destino del inmueble sera exclusivamente el de VIVIENDA UNICA Y DE USO FAMILIAR del LOCATARIO y de su grupo conviviente, conforme art. 1194 del CCyC.`)

  y = clausulaTitulo(doc, y, 'SEGUNDA', 'Plazo')
  y = parrafo(doc, y, `El plazo de la locacion sera desde el ${fmtFecha(contrato.fecha_inicio)} hasta el ${fmtFecha(contrato.fecha_fin)}. Conforme al art. 1198 del CCyC y modificaciones del DNU 70/2023, el plazo minimo legal de locacion habitacional es de DOS (2) anos. Vencido el plazo y de no mediar voluntad expresa de continuar la relacion locativa, las partes se ajustaran al regimen extintivo previsto por el CCyC.`)

  y = clausulaTitulo(doc, y, 'TERCERA', 'Precio del alquiler')
  y = parrafo(doc, y, `Las partes convienen como precio mensual y consecutivo del alquiler la suma de ${fmtMoneda(contrato.monto_inicial)} (PESOS), pagaderos del 1 al 10 de cada mes en el domicilio que indique el LOCADOR o por transferencia bancaria a la cuenta que se informe. La falta de pago en termino producira la mora automatica, sin necesidad de interpelacion alguna.`)

  y = clausulaTitulo(doc, y, 'CUARTA', 'Actualizacion del precio')
  const indiceTexto = {
    ipc: 'IPC (Indice de Precios al Consumidor) publicado por el INDEC',
    icl: 'ICL (Indice para Contratos de Locacion) publicado por el BCRA',
    fijo: `un porcentaje fijo del ${contrato.porcentaje_fijo || 0}%`,
    sin_ajuste: 'sin ajuste de actualizacion',
  }[contrato.indice_ajuste] || 'el indice convenido'
  y = parrafo(doc, y, `El precio se actualizara cada ${contrato.periodicidad_meses || 3} meses contados desde el inicio de la locacion, conforme a ${indiceTexto}. El nuevo valor regira a partir del primer dia del mes inmediato posterior a cada periodo. Las partes podran pactar la actualizacion mediante el indice que mejor refleje las condiciones economicas vigentes al momento de cada ajuste.`)

  y = clausulaTitulo(doc, y, 'QUINTA', 'Deposito en garantia')
  y = parrafo(doc, y, `EL LOCATARIO entrega en este acto al LOCADOR la suma de ${fmtMoneda(contrato.deposito)} en concepto de deposito en garantia, que sera restituido al finalizar la locacion previa verificacion del estado de conservacion del inmueble y cancelacion de las obligaciones a cargo del LOCATARIO (servicios, expensas, impuestos), conforme art. 1196 del CCyC.`)

  y = clausulaTitulo(doc, y, 'SEXTA', 'Servicios, expensas e impuestos')
  y = parrafo(doc, y, `Estaran a cargo del LOCATARIO los servicios de luz, gas, agua, telefono, internet, ABL y todo otro servicio inherente al uso del inmueble. Las expensas ordinarias del consorcio quedan a cargo del LOCATARIO; las extraordinarias y los gastos de inversion edilicia quedan a cargo del LOCADOR. El impuesto inmobiliario quedara a cargo del LOCADOR.`)

  y = clausulaTitulo(doc, y, 'SEPTIMA', 'Conservacion y mejoras')
  y = parrafo(doc, y, `El LOCATARIO recibe el inmueble en perfecto estado de conservacion, debiendo restituirlo en el mismo estado, salvo el deterioro derivado del uso normal y diligente. Toda mejora realizada por el LOCATARIO quedara en beneficio del inmueble sin derecho a indemnizacion, salvo pacto expreso por escrito.`)

  y = clausulaTitulo(doc, y, 'OCTAVA', 'Rescision anticipada')
  y = parrafo(doc, y, `El LOCATARIO podra rescindir el contrato en cualquier momento, debiendo notificar fehacientemente al LOCADOR con SESENTA (60) dias de anticipacion. La indemnizacion por rescision anticipada sera la prevista en el art. 1221 del CCyC: equivalente a UN (1) mes y MEDIO (1/2) de alquiler si la rescision se produce dentro del primer ano, y UN (1) mes si la rescision se produce con posterioridad.`)

  y = clausulaTitulo(doc, y, 'NOVENA', 'Domicilios y jurisdiccion')
  y = parrafo(doc, y, `Las partes constituyen domicilios especiales en los indicados precedentemente, donde se tendran por validas todas las notificaciones que se cursen. Para cualquier divergencia que pudiera suscitarse con motivo del presente, las partes se someten a la jurisdiccion de los Tribunales Ordinarios competentes, con renuncia a todo otro fuero o jurisdiccion que pudiera corresponder.`)

  if (contrato.notas) {
    y = clausulaTitulo(doc, y, 'DECIMA', 'Notas adicionales')
    y = parrafo(doc, y, contrato.notas)
  }

  // siempre dejar firmas en pagina nueva si no hay espacio
  if (y > H - 80) doc.addPage()
  firmas(doc, 'LOCADOR', 'LOCATARIO')
  footer(doc, codigo)
  doc.save(`${codigo}-alquiler-vivienda.pdf`)
}

// ---------- TEMPLATE: ALQUILER COMERCIAL (CCyC) ----------

function pdfAlquilerComercial({ contrato, propiedad, propietario, inquilino }) {
  const doc = nuevoDocumento()
  const codigo = contrato.codigo || `ALQ-${contrato.id}`
  header(doc, 'CONTRATO DE LOCACION COMERCIAL', 'Inmueble con destino comercial', codigo)

  let y = 54
  const intro = `En la Ciudad de Buenos Aires, a los ${fmtFecha(contrato.fecha_inicio)}, entre las partes que a continuacion se identifican, se celebra el presente CONTRATO DE LOCACION DE INMUEBLE CON DESTINO COMERCIAL, sujeto a las disposiciones del Codigo Civil y Comercial de la Nacion (arts. 1187 a 1226), conforme a las siguientes clausulas:`
  y = parrafo(doc, y, intro)

  y = bloqueParte(doc, y, 'LOCADOR (propietario)', clienteCompleto(propietario))
  y = bloqueParte(doc, y, 'LOCATARIO (inquilino comercial)', clienteCompleto(inquilino))

  y = clausulaTitulo(doc, y, 'PRIMERA', 'Objeto y destino')
  y = parrafo(doc, y, `EL LOCADOR da en locacion al LOCATARIO, quien acepta de conformidad, el inmueble ubicado en ${propiedad?.direccion || 'sin especificar'}, ${propiedad?.ciudad || ''}, ${propiedad?.provincia || ''}. El destino sera EXCLUSIVAMENTE COMERCIAL, no pudiendo el LOCATARIO modificar dicho destino sin autorizacion previa y por escrito del LOCADOR. El LOCATARIO declara que sera el unico responsable por las habilitaciones municipales, sanitarias y de seguridad necesarias para el desarrollo de su actividad.`)

  y = clausulaTitulo(doc, y, 'SEGUNDA', 'Plazo de locacion')
  y = parrafo(doc, y, `El plazo de la locacion sera desde el ${fmtFecha(contrato.fecha_inicio)} hasta el ${fmtFecha(contrato.fecha_fin)}. Conforme al art. 1199 del CCyC, el plazo minimo legal para destino distinto al habitacional es de TRES (3) anos. Las partes podran pactar la prorroga del contrato mediante acuerdo expreso celebrado con anterioridad al vencimiento.`)

  y = clausulaTitulo(doc, y, 'TERCERA', 'Precio y forma de pago')
  y = parrafo(doc, y, `Las partes convienen como precio mensual del alquiler la suma de ${fmtMoneda(contrato.monto_inicial)} (PESOS), pagaderos del 1 al 10 de cada mes. Si el LOCADOR fuera responsable inscripto en el IVA, el precio se vera incrementado por el IVA correspondiente. La mora se producira de pleno derecho por el solo vencimiento del plazo, sin necesidad de interpelacion judicial o extrajudicial.`)

  y = clausulaTitulo(doc, y, 'CUARTA', 'Actualizacion del precio')
  const indiceTextoComercial = {
    ipc: 'IPC (Indice de Precios al Consumidor) publicado por el INDEC',
    icl: 'ICL (Indice para Contratos de Locacion) publicado por el BCRA',
    fijo: `un porcentaje fijo del ${contrato.porcentaje_fijo || 0}%`,
    sin_ajuste: 'sin ajuste de actualizacion',
  }[contrato.indice_ajuste] || 'el indice convenido'
  y = parrafo(doc, y, `El precio se actualizara cada ${contrato.periodicidad_meses || 6} meses contados desde el inicio de la locacion, conforme a ${indiceTextoComercial}. En contratos comerciales, las partes son libres de pactar el indice y la periodicidad de actualizacion que mejor se ajuste a su actividad y al riesgo economico asumido.`)

  y = clausulaTitulo(doc, y, 'QUINTA', 'Deposito en garantia')
  y = parrafo(doc, y, `EL LOCATARIO entrega en este acto al LOCADOR la suma de ${fmtMoneda(contrato.deposito)} en concepto de deposito en garantia, equivalente a multiples meses de alquiler dada la naturaleza comercial del contrato. Sera restituido al finalizar la locacion previa verificacion del estado del inmueble y cancelacion de las obligaciones del LOCATARIO.`)

  y = clausulaTitulo(doc, y, 'SEXTA', 'Servicios, expensas e impuestos')
  y = parrafo(doc, y, `Quedaran a cargo del LOCATARIO la totalidad de los servicios e impuestos vinculados al uso del inmueble: luz, gas, agua, ABL, expensas (ordinarias y extraordinarias salvo pacto en contrario), tasas municipales por habilitacion comercial, seguridad e higiene, y todo otro tributo nacional, provincial o municipal vinculado a la actividad comercial desarrollada en el inmueble.`)

  y = clausulaTitulo(doc, y, 'SEPTIMA', 'Habilitaciones y mejoras')
  y = parrafo(doc, y, `EL LOCATARIO sera el unico responsable de obtener y mantener vigentes las habilitaciones municipales, sanitarias, bromatologicas y de seguridad que correspondan a su actividad comercial. Toda mejora, refaccion o instalacion realizada por el LOCATARIO quedara en beneficio del inmueble al finalizar la locacion sin derecho a reclamo, salvo pacto expreso en contrario por escrito.`)

  y = clausulaTitulo(doc, y, 'OCTAVA', 'Rescision y resolucion')
  y = parrafo(doc, y, `EL LOCATARIO podra rescindir anticipadamente el contrato notificando al LOCADOR con NOVENTA (90) dias de anticipacion mediante carta documento o medio fehaciente equivalente. La indemnizacion sera de DOS (2) meses de alquiler si la rescision se produjera dentro del primer ano, y UN (1) mes en lo sucesivo. La falta de pago de DOS (2) periodos consecutivos facultara al LOCADOR a resolver el contrato sin necesidad de interpelacion alguna.`)

  y = clausulaTitulo(doc, y, 'NOVENA', 'Domicilios y jurisdiccion')
  y = parrafo(doc, y, `Las partes constituyen domicilios especiales en los indicados ut supra, donde se tendran por validas todas las notificaciones. Para cualquier divergencia derivada del presente contrato, las partes se someten expresamente a la jurisdiccion de los Tribunales Ordinarios Comerciales de la Ciudad Autonoma de Buenos Aires, con renuncia a todo otro fuero o jurisdiccion.`)

  if (contrato.notas) {
    y = clausulaTitulo(doc, y, 'DECIMA', 'Notas adicionales')
    y = parrafo(doc, y, contrato.notas)
  }

  if (y > H - 80) doc.addPage()
  firmas(doc, 'LOCADOR', 'LOCATARIO COMERCIAL')
  footer(doc, codigo)
  doc.save(`${codigo}-alquiler-comercial.pdf`)
}

// ---------- TEMPLATE: BOLETO DE COMPRAVENTA ----------

function pdfBoletoCompraventa({ contrato, propiedad, propietario, inquilino }) {
  const doc = nuevoDocumento()
  const codigo = contrato.codigo || `BOL-${contrato.id}`
  header(doc, 'BOLETO DE COMPRAVENTA', 'Compromiso de venta inmueble', codigo)

  let y = 54
  const intro = `En la Ciudad de Buenos Aires, a los ${fmtFecha(contrato.fecha_inicio)}, entre las partes que a continuacion se identifican, se celebra el presente BOLETO DE COMPRAVENTA INMOBILIARIA, sujeto a las disposiciones del Codigo Civil y Comercial de la Nacion (arts. 1170 a 1185), conforme a las siguientes clausulas:`
  y = parrafo(doc, y, intro)

  y = bloqueParte(doc, y, 'VENDEDOR', clienteCompleto(propietario))
  y = bloqueParte(doc, y, 'COMPRADOR', clienteCompleto(inquilino))

  y = clausulaTitulo(doc, y, 'PRIMERA', 'Objeto')
  y = parrafo(doc, y, `EL VENDEDOR vende y EL COMPRADOR compra, libre de toda deuda, gravamen, embargo, inhibicion u ocupante, el inmueble ubicado en ${propiedad?.direccion || 'sin especificar'}, ${propiedad?.ciudad || ''}, ${propiedad?.provincia || ''}, con una superficie aproximada de ${propiedad?.superficie_m2 || 0} m2, conforme constancias de dominio que se acompanan al presente. La identificacion catastral, partida inmobiliaria y matricula registral se completaran en la escritura traslativa de dominio.`)

  y = clausulaTitulo(doc, y, 'SEGUNDA', 'Precio total')
  y = parrafo(doc, y, `El precio total y definitivo de la operacion se fija en ${fmtMoneda(contrato.monto_inicial)}, que sera abonado por EL COMPRADOR al VENDEDOR de la siguiente forma: (a) la suma de ${fmtMoneda(contrato.deposito)} en concepto de SENA y a cuenta del precio, abonada en este acto, sirviendo el presente como recibo y carta de pago; (b) el saldo restante sera abonado en oportunidad de la firma de la escritura traslativa de dominio.`)

  y = clausulaTitulo(doc, y, 'TERCERA', 'Sena - principio de ejecucion')
  y = parrafo(doc, y, `La sena entregada en este acto reviste el caracter de PRINCIPIO DE EJECUCION del contrato, conforme art. 1059 del CCyC, no funcionando como sena penitencial. En consecuencia, ninguna de las partes podra retractarse, salvo lo dispuesto en la clausula sobre clausula penal. La operacion queda perfeccionada con la suscripcion del presente y la entrega de la sena.`)

  y = clausulaTitulo(doc, y, 'CUARTA', 'Escritura traslativa')
  y = parrafo(doc, y, `Las partes acuerdan que la escritura publica traslativa de dominio se otorgara dentro del plazo que vencera el ${fmtFecha(contrato.fecha_fin)}, ante el escribano que designe EL COMPRADOR. EL VENDEDOR se obliga a presentar en dicha oportunidad la totalidad de la documentacion necesaria: titulos, planos, libre deuda de impuestos, expensas y servicios. Los gastos de escrituracion seran soportados por las partes conforme uso y costumbre de plaza.`)

  y = clausulaTitulo(doc, y, 'QUINTA', 'Posesion')
  y = parrafo(doc, y, `La posesion del inmueble se entregara al COMPRADOR libre de ocupantes, muebles y enseres, en oportunidad de la firma de la escritura traslativa de dominio y previo pago integro del saldo del precio convenido. Hasta dicho momento, el inmueble permanecera en poder del VENDEDOR, quien sera responsable por su conservacion.`)

  y = clausulaTitulo(doc, y, 'SEXTA', 'Estado del inmueble')
  y = parrafo(doc, y, `EL COMPRADOR declara conocer y aceptar el estado actual de conservacion del inmueble, manifestando que la operacion se realiza en el estado en que el bien se encuentra al dia de la fecha. EL VENDEDOR garantiza encontrarse en plena posesion del inmueble, libre de toda restriccion de dominio, embargo, inhibicion, hipoteca o gravamen.`)

  y = clausulaTitulo(doc, y, 'SEPTIMA', 'Clausula penal')
  y = parrafo(doc, y, `Para el supuesto de incumplimiento de cualquiera de las partes, la parte cumplidora podra optar entre: (a) demandar el cumplimiento forzado del contrato; o (b) resolver el contrato y reclamar a la incumplidora una multa equivalente al CIEN POR CIENTO (100%) de la sena entregada, sin perjuicio de las indemnizaciones por danos y perjuicios que correspondieran.`)

  y = clausulaTitulo(doc, y, 'OCTAVA', 'Comision inmobiliaria')
  y = parrafo(doc, y, `Las partes reconocen que la operacion ha sido gestionada por CIUDAD. en su calidad de inmobiliaria intermediaria, comprometiendose cada parte al pago de la comision pactada del ${contrato.comision_porc || 3}% sobre el precio total de la operacion, conforme uso y costumbre de plaza, pagadera al momento de la escritura.`)

  y = clausulaTitulo(doc, y, 'NOVENA', 'Domicilios y jurisdiccion')
  y = parrafo(doc, y, `Las partes constituyen domicilios especiales en los indicados precedentemente, donde se tendran por validas todas las notificaciones cursadas. Para toda divergencia derivada del presente, las partes se someten expresamente a la jurisdiccion de los Tribunales Ordinarios competentes, con renuncia a todo otro fuero o jurisdiccion.`)

  if (contrato.notas) {
    y = clausulaTitulo(doc, y, 'DECIMA', 'Notas adicionales')
    y = parrafo(doc, y, contrato.notas)
  }

  if (y > H - 80) doc.addPage()
  firmas(doc, 'VENDEDOR', 'COMPRADOR')
  footer(doc, codigo)
  doc.save(`${codigo}-boleto-compraventa.pdf`)
}

// ---------- entrada publica ----------

export function generarPDFContrato(args) {
  const tipo = args?.contrato?.tipo
  if (tipo === 'alquiler_comercial') return pdfAlquilerComercial(args)
  if (tipo === 'boleto_compraventa') return pdfBoletoCompraventa(args)
  return pdfAlquilerVivienda(args)
}
