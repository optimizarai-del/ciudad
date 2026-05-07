// CIUDAD. Inmobiliaria - Generador de PDFs legales por tipo de contrato.
// Modelo Santa Rosa, La Pampa. Tres plantillas:
//   - Alquiler Vivienda (modelo CIUDAD, ICL, plazo 1 ano, fiadores, pagare, seguro)
//   - Alquiler Comercial (CCyC arts. 1187-1226)
//   - Boleto de Compraventa (CCyC arts. 1170-1185)
import { jsPDF } from 'jspdf'

// ── Datos de la empresa CIUDAD Inmobiliaria ──
export const EMPRESA = {
  nombre: 'CIUDAD. Inmobiliaria',
  domicilio_comercial: 'Av. Uruguay 268',
  domicilio_legal: 'Gral. Savio 1260',
  ciudad: 'Santa Rosa',
  provincia: 'La Pampa',
  jurisdiccion: 'la justicia ordinaria de la ciudad de Santa Rosa, Pcia. de La Pampa',
}

const W = 210
const H = 297
const M = 22
const COL_BG_DARK   = [10, 10, 10]
const COL_BG_LIGHT  = [247, 247, 247]
const COL_TEXT      = [10, 10, 10]
const COL_MUTED     = [115, 115, 115]
const COL_SOFT      = [200, 200, 200]
const COL_WHITE     = [255, 255, 255]

// ──────────── helpers ────────────

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
  doc.text(`${EMPRESA.domicilio_comercial} - ${EMPRESA.ciudad}, ${EMPRESA.provincia}`, M, 20)
  doc.setFontSize(10)
  doc.setFont('helvetica', 'bold')
  doc.text(codigo || '', W - M, 14, { align: 'right' })
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.text(subtitulo || '', W - M, 20, { align: 'right' })

  doc.setTextColor(...COL_TEXT)
  doc.setFontSize(13)
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
    doc.text(`${EMPRESA.nombre} - ${EMPRESA.ciudad}, ${EMPRESA.provincia}`, M, H - 9)
    doc.text(`${codigo || ''}  -  Pag. ${i} de ${pages}`, W - M, H - 9, { align: 'right' })
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
  doc.text(`${numero}: ${titulo.toUpperCase()}`, M + 3, y + 4.8)
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
  const lines = doc.splitTextToSize(String(valor || '—'), W - M * 2 - 60)
  doc.text(lines, M + 60, y)
  return y + Math.max(6, lines.length * 5)
}

function firmasTriple(doc, lblIzq, lblCentro, lblDer) {
  const y = H - 50
  doc.setDrawColor(...COL_SOFT)
  doc.setLineWidth(0.4)
  // tres líneas de firma
  const w = 50
  const x1 = M
  const x3 = W - M - w
  const x2 = (x1 + x3) / 2
  doc.line(x1, y, x1 + w, y)
  doc.line(x2, y, x2 + w, y)
  doc.line(x3, y, x3 + w, y)
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(...COL_MUTED)
  doc.text(lblIzq,    x1 + w / 2, y + 5, { align: 'center' })
  doc.text(lblCentro, x2 + w / 2, y + 5, { align: 'center' })
  doc.text(lblDer,    x3 + w / 2, y + 5, { align: 'center' })
  doc.text('Firma y aclaracion', x1 + w / 2, y + 10, { align: 'center' })
  doc.text('Firma y aclaracion', x2 + w / 2, y + 10, { align: 'center' })
  doc.text('Firma y aclaracion', x3 + w / 2, y + 10, { align: 'center' })
}

function firmasDoble(doc, lblIzq, lblDer) {
  const y = H - 50
  doc.setDrawColor(...COL_SOFT)
  doc.setLineWidth(0.4)
  doc.line(M, y, M + 70, y)
  doc.line(W - M - 70, y, W - M, y)
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(...COL_MUTED)
  doc.text(lblIzq, M + 35, y + 5, { align: 'center' })
  doc.text(lblDer, W - M - 35, y + 5, { align: 'center' })
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

function clienteNombre(c) {
  if (!c) return ''
  return c.razon_social || `${c.nombre || ''} ${c.apellido || ''}`.trim()
}

function clienteDescriptivo(c) {
  // "JUAN PEREZ, Argentino, DNI 12.345.678" - estilo CIUDAD
  if (!c) return ''
  const nombre = (c.razon_social || `${c.apellido || ''} ${c.nombre || ''}`.trim()).toUpperCase()
  const nac = c.nacionalidad || 'Argentino'
  const doc = c.documento ? `DNI N° ${c.documento}` : ''
  return [nombre, nac, doc].filter(Boolean).join(', ')
}

function clienteCompleto(c, fallback = 'Sin asignar') {
  if (!c) return { nombre: fallback, nac: '', dni: '', tel: '', email: '', dir: '' }
  const nombre = c.razon_social || `${c.apellido || ''} ${c.nombre || ''}`.trim() || fallback
  const dirParts = [c.direccion, c.localidad, c.provincia].filter(Boolean)
  return {
    nombre: nombre.toUpperCase(),
    nac: c.nacionalidad || 'Argentino',
    dni: c.documento || '',
    tel: c.telefono || '',
    email: c.email || '',
    dir: dirParts.join(', '),
  }
}

function bloqueParte(doc, y, etiqueta, parte) {
  y = ensureSpace(doc, y, 30)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  doc.setTextColor(...COL_MUTED)
  doc.text(etiqueta.toUpperCase(), M, y)
  y += 6
  y = dato(doc, y, 'Nombre / Razon social', parte.nombre)
  if (parte.nac)   y = dato(doc, y, 'Nacionalidad',          parte.nac)
  if (parte.dni)   y = dato(doc, y, 'DNI / CUIT',            parte.dni)
  if (parte.dir)   y = dato(doc, y, 'Domicilio',             parte.dir)
  if (parte.tel)   y = dato(doc, y, 'Telefono',              parte.tel)
  if (parte.email) y = dato(doc, y, 'Email',                 parte.email)
  return y + 3
}

// ──────────── ALQUILER VIVIENDA — modelo CIUDAD Santa Rosa ────────────

function pdfAlquilerVivienda({ contrato, propiedad, propietario, inquilino, fiador, fiador2 }) {
  const doc = nuevoDocumento()
  const codigo = contrato.codigo || `ALQ-${contrato.id}`
  const ciudadOp = propiedad?.ciudad || EMPRESA.ciudad
  const provinciaOp = propiedad?.provincia || EMPRESA.provincia

  header(doc, 'CONTRATO DE LOCACION', 'Inmueble - destino vivienda familiar', codigo)

  let y = 54
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  doc.setTextColor(...COL_TEXT)

  const intro = `En la ciudad de ${EMPRESA.ciudad}, Provincia de ${EMPRESA.provincia}, a los ${fmtFecha(contrato.fecha_inicio)}, entre ${clienteDescriptivo(propietario) || 'EL/LA LOCADOR/A (a completar)'}, por una parte en adelante "EL/LA LOCADOR/A", y ${clienteDescriptivo(inquilino) || 'EL/LA LOCATARIO/A (a completar)'}, por la otra en adelante "EL/LA LOCATARIO/A", convienen en celebrar el siguiente contrato de LOCACION, sujeto a las siguientes clausulas y condiciones:`
  y = parrafo(doc, y, intro)

  y = bloqueParte(doc, y, 'LOCADOR/A', clienteCompleto(propietario))
  y = bloqueParte(doc, y, 'LOCATARIO/A', clienteCompleto(inquilino))

  // ── PRIMERO: Objeto e inventario ──
  y = clausulaTitulo(doc, y, 'PRIMERO', 'Objeto, estado e inventario')
  let objeto = `EL/LA LOCADOR/A entrega en locacion al/a la LOCATARIO/A, quien declara haber visto el inmueble y reconocer el BUEN ESTADO en que se encuentra, aceptando en este acto a su entera conformidad, el inmueble ubicado en ${propiedad?.direccion || 'a completar'}, ${ciudadOp}, Pcia. de ${provinciaOp}.`
  if (propiedad?.descripcion) {
    objeto += ` Descripcion: ${propiedad.descripcion}`
  }
  y = parrafo(doc, y, objeto)

  if (contrato.inventario) {
    y = parrafo(doc, y, `INVENTARIO Y BIENES INCORPORADOS: ${contrato.inventario}`)
    y = parrafo(doc, y, 'EL/LA LOCATARIO/A se obliga a devolver el inmueble en las mismas condiciones de pintura (latex blanco color original) y con todos los artefactos detallados en perfecto funcionamiento. Todo se registra bajo archivo fotografico que se acompana al presente.')
  } else {
    y = parrafo(doc, y, 'EL/LA LOCATARIO/A se obliga a devolver el inmueble en el mismo estado de conservacion y pintura en que lo recibe. Las condiciones de entrega se documentan mediante archivo fotografico que se acompana al presente.')
  }

  // ── SEGUNDO: Destino ──
  y = clausulaTitulo(doc, y, 'SEGUNDO', 'Destino')
  y = parrafo(doc, y, 'EL/LA LOCATARIO/A declara que destinara el inmueble locado unica y exclusivamente para uso familiar, quedando prohibido cambiar el destino mencionado, asi como cederlo, sublocarlo o prestarlo a terceros bajo cualquier titulo.')

  // ── TERCERO: Precio y forma de pago ──
  y = clausulaTitulo(doc, y, 'TERCERO', 'Precio y forma de pago')
  const indiceTexto = {
    ipc: 'IPC (Indice de Precios al Consumidor) publicado por el INDEC',
    icl: 'ICL (Indice para Contratos de Locacion) publicado mensualmente por el Banco Central de la Republica Argentina',
    fijo: `un porcentaje fijo del ${contrato.porcentaje_fijo || 0}%`,
    sin_ajuste: 'sin ajuste de actualizacion',
  }[contrato.indice_ajuste] || 'el indice convenido'
  const dDesde = contrato.dia_pago_desde ?? 1
  const dHasta = contrato.dia_pago_hasta ?? 7
  const punicion = contrato.punicion_diaria_porc ?? 1
  y = parrafo(doc, y, `Queda convenido entre las partes que EL/LA LOCATARIO/A abonara un alquiler mensual inicial de ${fmtMoneda(contrato.monto_inicial)} (PESOS), mas Tasa Municipal y Expensas Ordinarias. Los servicios de luz electrica, gas natural, agua, internet y demas inherentes al uso del inmueble corren por exclusiva cuenta del/de la LOCATARIO/A. Las partes libremente acuerdan corregir el valor cada ${contrato.periodicidad_meses || 3} meses, segun ${indiceTexto}, para evitar el desequilibrio de las prestaciones reciprocas que genera la desvalorizacion del signo monetario. Los alquileres se abonaran del ${dDesde} al ${dHasta} de cada mes en el domicilio de la inmobiliaria interviniente - ${EMPRESA.domicilio_comercial}, ${EMPRESA.ciudad} - o donde EL/LA LOCADOR/A lo disponga. Para el caso de atraso en el pago, EL/LA LOCATARIO/A sufrira una PUNICION DIARIA DEL ${punicion}% a partir del dia ${dHasta + 1} del mes que corresponda. El pago se entiende por periodos mensuales adelantados completos.`)

  // ── CUARTO: Plazo y resolucion anticipada ──
  y = clausulaTitulo(doc, y, 'CUARTO', 'Plazo y resolucion anticipada')
  y = parrafo(doc, y, `El plazo de la presente locacion se fija de comun acuerdo desde el ${fmtFecha(contrato.fecha_inicio)} hasta el ${fmtFecha(contrato.fecha_fin)}, ambas fechas inclusive. EL/LA LOCATARIO/A podra resolver anticipadamente el contrato siempre que hubieren transcurrido SEIS (6) meses desde su inicio, debiendo notificar fehacientemente su decision al/a la LOCADOR/A con al menos UN (1) mes de anticipacion y abonar en concepto de indemnizacion una penalizacion equivalente a UN (1) mes de alquiler vigente al momento de la rescision.`)

  // ── QUINTO: Obligaciones del locatario ──
  y = clausulaTitulo(doc, y, 'QUINTO', 'Obligaciones del/de la locatario/a')
  y = parrafo(doc, y, 'EL/LA LOCATARIO/A se obliga a: a) no ceder total o parcialmente el contrato, sea a titulo oneroso o gratuito, ni sublocar el inmueble en forma alguna, bajo apercibimiento de rescision culpable; b) no modificar el destino acordado en la clausula SEGUNDA; c) no realizar mejoras ni modificaciones en el inmueble sin la autorizacion previa y escrita del/de la LOCADOR/A; d) justificar la devolucion del inmueble unicamente mediante documento escrito emanado del/de la LOCADOR/A o sus representantes, no admitiendose otro medio de prueba.')

  // ── SEXTO: Conservacion y reparaciones ──
  y = clausulaTitulo(doc, y, 'SEXTO', 'Conservacion y reparaciones')
  y = parrafo(doc, y, 'EL/LA LOCATARIO/A recibe el inmueble en buen estado de conservacion, comprometiendose a mantenerlo en las mismas condiciones, tomando a su cargo las reparaciones de roturas y desperfectos que se originen en la propiedad y sus instalaciones, salvo las derivadas del uso normal o desperfectos de construccion. Sera responsable de los danos causados por el/la LOCATARIO/A, sus dependientes o cualquier persona que ingrese al inmueble con su autorizacion. EL/LA LOCATARIO/A debera restituir el inmueble pintado al latex de primera calidad - color original - y con los artefactos en perfecto funcionamiento.')

  // ── SEPTIMO: Eximicion de responsabilidad ──
  y = clausulaTitulo(doc, y, 'SEPTIMO', 'Eximicion de responsabilidad')
  y = parrafo(doc, y, 'EL/LA LOCADOR/A no se hace responsable ni reconocera indemnizacion alguna proveniente de danos materiales o fisicos causados al/a la LOCATARIO/A, terceros, mercaderias, vehiculos o bienes, originados por la propiedad locada, sus instalaciones, servicios, incendios, movimientos sismicos, inundaciones, derrumbes, granizos, vientos o cualquier otro tipo de accidentes.')

  // ── OCTAVO: Multas, mascotas y convivencia ──
  y = clausulaTitulo(doc, y, 'OCTAVO', 'Multas municipales, mascotas y convivencia')
  let octavo = 'EL/LA LOCATARIO/A sera responsable de cualquier multa que se aplicare al inmueble por transgresiones o disposiciones municipales. El Impuesto Inmobiliario sera pagado por EL/LA LOCADOR/A. '
  if (contrato.permite_mascotas) {
    octavo += 'Se permite el ingreso de mascotas, debiendo EL/LA LOCATARIO/A responsabilizarse por cualquier dano que estas pudieran causar al inmueble o a las partes comunes del edificio. '
  } else {
    octavo += 'Queda PROHIBIDO al/a la LOCATARIO/A introducir mascotas tanto al edificio como al departamento donde habita. '
  }
  octavo += 'EL/LA LOCATARIO/A debera respetar y ajustarse a las normas de convivencia establecidas en los reglamentos de copropiedad - horarios de descanso, no producir ruidos molestos, etc.'
  y = parrafo(doc, y, octavo)

  // ── NOVENO: Seguro ──
  if (contrato.seguro_obligatorio !== false) {
    y = clausulaTitulo(doc, y, 'NOVENO', 'Seguro')
    y = parrafo(doc, y, 'EL/LA LOCATARIO/A debera constituir, durante toda la vigencia del presente contrato y hasta la restitucion del inmueble, un Seguro contra incendio, robo y responsabilidad civil, quedando EL/LA LOCADOR/A exento/a de tal responsabilidad y obligacion contraida.')
  }

  // ── DECIMO: Mora ──
  y = clausulaTitulo(doc, y, 'DECIMO', 'Mora e incumplimiento')
  y = parrafo(doc, y, `El incumplimiento por parte del/de la LOCATARIO/A de cualquiera de las obligaciones contraidas, y en especial la falta de pago de un solo periodo de alquiler en la fecha y lugar establecidos, lo hara incurrir en mora de pleno derecho, sin necesidad de requerimiento judicial ni extrajudicial, quedando facultado/a EL/LA LOCADOR/A para ejercer todas las acciones legales correspondientes. EL/LA LOCATARIO/A autoriza expresamente al/a la LOCADOR/A a solicitar la homologacion judicial del presente contrato y demandar el correspondiente allanamiento, extensivo a cualquier ocupante. La punicion diaria del ${punicion}% sobre el monto adeudado se aplicara desde el dia ${dHasta + 1} del mes que corresponda.`)

  // ── DECIMO PRIMERO: Inspeccion ──
  y = clausulaTitulo(doc, y, 'DECIMO PRIMERO', 'Inspeccion del inmueble')
  y = parrafo(doc, y, 'EL/LA LOCATARIO/A debera permitir al/a la LOCADOR/A o su representante inspeccionar el inmueble previo aviso. Mantendra en condiciones las instalaciones y artefactos electricos, de gas natural, sanitarias y caneras propias del inmueble.')

  // ── DECIMO SEGUNDO: Fiadores y pagare refuerzo ──
  if (fiador || fiador2 || (contrato.pagare_refuerzo && contrato.pagare_refuerzo > 0)) {
    y = clausulaTitulo(doc, y, 'DECIMO SEGUNDO', 'Fiadores solidarios y pagare refuerzo')
    let f = 'Se constituyen en fiadores, lisos, llanos y principales pagadores de los alquileres y de toda obligacion emergente del presente contrato, asumiendo la garantia hasta la finalizacion del mismo y/o la entrega efectiva de la propiedad'
    const fs = []
    if (fiador) fs.push(clienteDescriptivo(fiador) + (fiador.direccion ? `, con domicilio en ${fiador.direccion}, ${fiador.localidad || ''}, Pcia. de ${fiador.provincia || EMPRESA.provincia}` : '') + (fiador.telefono ? `, telefono ${fiador.telefono}` : ''))
    if (fiador2) fs.push(clienteDescriptivo(fiador2) + (fiador2.direccion ? `, con domicilio en ${fiador2.direccion}, ${fiador2.localidad || ''}, Pcia. de ${fiador2.provincia || EMPRESA.provincia}` : '') + (fiador2.telefono ? `, telefono ${fiador2.telefono}` : ''))
    if (fs.length) f += ': ' + fs.join('; ') + '. '
    else f += ' (a completar al momento de la firma). '
    f += 'Ambos garantes presentan en este acto constancia de recibos de sueldo actualizados.'
    y = parrafo(doc, y, f)

    if (contrato.pagare_refuerzo && contrato.pagare_refuerzo > 0) {
      y = parrafo(doc, y, `Asimismo, en caracter complementario, EL/LA LOCATARIO/A suscribe y entrega un PAGARE a favor del/de la LOCADOR/A por la suma de ${fmtMoneda(contrato.pagare_refuerzo)}, como refuerzo de las obligaciones emergentes del presente contrato.`)
    }
  }

  // ── DECIMO TERCERO: Deposito ──
  y = clausulaTitulo(doc, y, 'DECIMO TERCERO', 'Deposito en garantia')
  y = parrafo(doc, y, `EL/LA LOCATARIO/A entrega en este acto al/a la LOCADOR/A la suma de ${fmtMoneda(contrato.deposito)} en concepto de DEPOSITO EN GARANTIA del fiel cumplimiento del presente contrato. Dicha suma no generara intereses ni podra ser aplicada al pago de alquileres, y le sera devuelta al efectivo reintegro del inmueble en las condiciones pactadas, o se afectara para cubrir faltantes, roturas, deterioros o cualquier otra deuda con EL/LA LOCADOR/A.`)

  // ── DECIMO CUARTO: Domicilios ──
  y = clausulaTitulo(doc, y, 'DECIMO CUARTO', 'Domicilios especiales')
  y = parrafo(doc, y, `Para todos los efectos legales del presente contrato y las acciones que de el emerjan, las partes constituyen domicilio legal y especial para notificaciones: EL/LA LOCADOR/A en ${propietario?.direccion ? `${propietario.direccion}, ${propietario.localidad || EMPRESA.ciudad}` : `${EMPRESA.domicilio_legal}, ${EMPRESA.ciudad}`}, y EL/LA LOCATARIO/A en el domicilio LOCADO.`)

  // ── DECIMO QUINTO: Jurisdiccion ──
  y = clausulaTitulo(doc, y, 'DECIMO QUINTO', 'Jurisdiccion')
  y = parrafo(doc, y, `Para cualquier juicio resultante de este contrato, las partes se someten a ${EMPRESA.jurisdiccion}, renunciando a cualquier otro fuero o jurisdiccion, y en especial al Fuero Federal. En prueba de conformidad a todo lo expuesto, se firman TRES (3) ejemplares de un mismo tenor y a un solo efecto, en la ciudad de ${EMPRESA.ciudad}, a los ${fmtFecha(contrato.fecha_inicio)}.`)

  if (contrato.notas) {
    y = clausulaTitulo(doc, y, 'NOTAS ADICIONALES', '')
    y = parrafo(doc, y, contrato.notas)
  }

  if (y > H - 80) doc.addPage()
  firmasTriple(doc, 'LOCADOR/A', 'LOCATARIO/A', 'GARANTES')
  footer(doc, codigo)
  doc.save(`${codigo}-alquiler-vivienda.pdf`)
}

// ──────────── ALQUILER COMERCIAL — CCyC + jurisdiccion Santa Rosa ────────────

function pdfAlquilerComercial({ contrato, propiedad, propietario, inquilino, fiador, fiador2 }) {
  const doc = nuevoDocumento()
  const codigo = contrato.codigo || `ALQ-${contrato.id}`
  const ciudadOp = propiedad?.ciudad || EMPRESA.ciudad
  const provinciaOp = propiedad?.provincia || EMPRESA.provincia

  header(doc, 'CONTRATO DE LOCACION COMERCIAL', 'Inmueble - destino comercial', codigo)

  let y = 54
  const intro = `En la ciudad de ${EMPRESA.ciudad}, Provincia de ${EMPRESA.provincia}, a los ${fmtFecha(contrato.fecha_inicio)}, entre ${clienteDescriptivo(propietario) || 'EL/LA LOCADOR/A (a completar)'}, por una parte en adelante "EL/LA LOCADOR/A", y ${clienteDescriptivo(inquilino) || 'EL/LA LOCATARIO/A (a completar)'}, por la otra en adelante "EL/LA LOCATARIO COMERCIAL", celebran el presente CONTRATO DE LOCACION CON DESTINO COMERCIAL, sujeto al Codigo Civil y Comercial de la Nacion (arts. 1187 a 1226) y a las siguientes clausulas:`
  y = parrafo(doc, y, intro)

  y = bloqueParte(doc, y, 'LOCADOR/A', clienteCompleto(propietario))
  y = bloqueParte(doc, y, 'LOCATARIO COMERCIAL', clienteCompleto(inquilino))

  y = clausulaTitulo(doc, y, 'PRIMERO', 'Objeto y destino')
  y = parrafo(doc, y, `EL/LA LOCADOR/A entrega en locacion al/a la LOCATARIO/A el inmueble ubicado en ${propiedad?.direccion || 'a completar'}, ${ciudadOp}, Pcia. de ${provinciaOp}, con destino EXCLUSIVAMENTE COMERCIAL. EL/LA LOCATARIO/A no podra modificar dicho destino sin autorizacion previa y escrita y sera el unico responsable por las habilitaciones municipales, sanitarias, bromatologicas y de seguridad necesarias para el desarrollo de su actividad.`)

  y = clausulaTitulo(doc, y, 'SEGUNDO', 'Plazo de locacion')
  y = parrafo(doc, y, `El plazo de la locacion se fija desde el ${fmtFecha(contrato.fecha_inicio)} hasta el ${fmtFecha(contrato.fecha_fin)}. Conforme al art. 1199 del CCyC, el plazo minimo legal para destino distinto al habitacional es de TRES (3) anos. Las partes podran pactar la prorroga mediante acuerdo expreso celebrado con anterioridad al vencimiento.`)

  y = clausulaTitulo(doc, y, 'TERCERO', 'Precio y forma de pago')
  const dDesde = contrato.dia_pago_desde ?? 1
  const dHasta = contrato.dia_pago_hasta ?? 7
  const punicion = contrato.punicion_diaria_porc ?? 1
  y = parrafo(doc, y, `Las partes convienen como precio mensual del alquiler la suma de ${fmtMoneda(contrato.monto_inicial)} (PESOS), pagaderos del ${dDesde} al ${dHasta} de cada mes en el domicilio de ${EMPRESA.nombre} - ${EMPRESA.domicilio_comercial}, ${EMPRESA.ciudad}. Si EL/LA LOCADOR/A fuera responsable inscripto en el IVA, el precio se incrementara con el IVA correspondiente. La mora se producira de pleno derecho por el solo vencimiento del plazo. Por cada dia de atraso a partir del dia ${dHasta + 1} se aplicara una punicion del ${punicion}% sobre el monto adeudado.`)

  y = clausulaTitulo(doc, y, 'CUARTO', 'Actualizacion del precio')
  const indiceTextoComercial = {
    ipc: 'IPC (Indice de Precios al Consumidor) publicado por el INDEC',
    icl: 'ICL (Indice para Contratos de Locacion) publicado por el BCRA',
    fijo: `un porcentaje fijo del ${contrato.porcentaje_fijo || 0}%`,
    sin_ajuste: 'sin ajuste de actualizacion',
  }[contrato.indice_ajuste] || 'el indice convenido'
  y = parrafo(doc, y, `El precio se actualizara cada ${contrato.periodicidad_meses || 6} meses segun ${indiceTextoComercial}. En contratos comerciales, las partes son libres de pactar el indice y la periodicidad de actualizacion que mejor se ajuste a su actividad y al riesgo economico asumido.`)

  y = clausulaTitulo(doc, y, 'QUINTO', 'Deposito en garantia')
  y = parrafo(doc, y, `EL/LA LOCATARIO/A entrega en este acto al/a la LOCADOR/A la suma de ${fmtMoneda(contrato.deposito)} en concepto de deposito en garantia, equivalente a multiples meses de alquiler dada la naturaleza comercial del contrato. Sera restituido al finalizar la locacion previa verificacion del estado del inmueble y cancelacion de las obligaciones del/de la LOCATARIO/A.`)

  y = clausulaTitulo(doc, y, 'SEXTO', 'Servicios, expensas e impuestos')
  y = parrafo(doc, y, 'Quedaran a cargo del/de la LOCATARIO/A la totalidad de los servicios e impuestos vinculados al uso del inmueble: luz, gas, agua, ABL, expensas (ordinarias y extraordinarias salvo pacto en contrario), tasas municipales por habilitacion comercial, seguridad e higiene, y todo otro tributo nacional, provincial o municipal vinculado a la actividad comercial desarrollada en el inmueble.')

  y = clausulaTitulo(doc, y, 'SEPTIMO', 'Habilitaciones y mejoras')
  y = parrafo(doc, y, 'EL/LA LOCATARIO/A sera el unico responsable de obtener y mantener vigentes las habilitaciones municipales, sanitarias, bromatologicas y de seguridad correspondientes a su actividad. Toda mejora, refaccion o instalacion realizada quedara en beneficio del inmueble al finalizar la locacion sin derecho a reclamo, salvo pacto expreso en contrario.')

  y = clausulaTitulo(doc, y, 'OCTAVO', 'Rescision y resolucion')
  y = parrafo(doc, y, 'EL/LA LOCATARIO/A podra rescindir anticipadamente el contrato notificando al/a la LOCADOR/A con NOVENTA (90) dias de anticipacion mediante carta documento o medio fehaciente equivalente. La indemnizacion sera de DOS (2) meses de alquiler si la rescision se produjera dentro del primer ano, y UN (1) mes en lo sucesivo. La falta de pago de DOS (2) periodos consecutivos facultara al/a la LOCADOR/A a resolver el contrato sin necesidad de interpelacion alguna.')

  if (contrato.seguro_obligatorio !== false) {
    y = clausulaTitulo(doc, y, 'NOVENO', 'Seguro')
    y = parrafo(doc, y, 'EL/LA LOCATARIO/A debera contratar y mantener vigente, durante toda la locacion, seguros de incendio, robo, responsabilidad civil hacia terceros y los especificos de la actividad comercial desarrollada en el inmueble.')
  }

  if (fiador || fiador2 || (contrato.pagare_refuerzo && contrato.pagare_refuerzo > 0)) {
    y = clausulaTitulo(doc, y, 'DECIMO', 'Fiadores y pagare refuerzo')
    let f = 'Se constituyen en fiadores, lisos, llanos y principales pagadores de las obligaciones emergentes del presente contrato'
    const fs = []
    if (fiador) fs.push(clienteDescriptivo(fiador) + (fiador.direccion ? `, con domicilio en ${fiador.direccion}, ${fiador.localidad || ''}, Pcia. de ${fiador.provincia || EMPRESA.provincia}` : ''))
    if (fiador2) fs.push(clienteDescriptivo(fiador2) + (fiador2.direccion ? `, con domicilio en ${fiador2.direccion}, ${fiador2.localidad || ''}, Pcia. de ${fiador2.provincia || EMPRESA.provincia}` : ''))
    if (fs.length) f += ': ' + fs.join('; ') + '.'
    else f += ' (a completar al momento de la firma).'
    y = parrafo(doc, y, f)
    if (contrato.pagare_refuerzo && contrato.pagare_refuerzo > 0) {
      y = parrafo(doc, y, `EL/LA LOCATARIO/A suscribe y entrega un PAGARE a favor del/de la LOCADOR/A por la suma de ${fmtMoneda(contrato.pagare_refuerzo)} como refuerzo complementario de las obligaciones del presente contrato.`)
    }
  }

  y = clausulaTitulo(doc, y, 'UNDECIMO', 'Domicilios y jurisdiccion')
  y = parrafo(doc, y, `Las partes constituyen domicilios especiales en los indicados precedentemente. Para toda divergencia derivada del presente contrato se someten a ${EMPRESA.jurisdiccion}, con renuncia a todo otro fuero o jurisdiccion.`)

  if (contrato.notas) {
    y = clausulaTitulo(doc, y, 'NOTAS ADICIONALES', '')
    y = parrafo(doc, y, contrato.notas)
  }

  if (y > H - 80) doc.addPage()
  firmasDoble(doc, 'LOCADOR/A', 'LOCATARIO COMERCIAL')
  footer(doc, codigo)
  doc.save(`${codigo}-alquiler-comercial.pdf`)
}

// ──────────── BOLETO DE COMPRAVENTA — CCyC + Santa Rosa ────────────

function pdfBoletoCompraventa({ contrato, propiedad, propietario, inquilino }) {
  const doc = nuevoDocumento()
  const codigo = contrato.codigo || `BOL-${contrato.id}`
  const ciudadOp = propiedad?.ciudad || EMPRESA.ciudad
  const provinciaOp = propiedad?.provincia || EMPRESA.provincia

  header(doc, 'BOLETO DE COMPRAVENTA', 'Compromiso de venta de inmueble', codigo)

  let y = 54
  const intro = `En la ciudad de ${EMPRESA.ciudad}, Provincia de ${EMPRESA.provincia}, a los ${fmtFecha(contrato.fecha_inicio)}, entre ${clienteDescriptivo(propietario) || 'EL/LA VENDEDOR/A (a completar)'}, en adelante "EL/LA VENDEDOR/A", y ${clienteDescriptivo(inquilino) || 'EL/LA COMPRADOR/A (a completar)'}, en adelante "EL/LA COMPRADOR/A", celebran el presente BOLETO DE COMPRAVENTA INMOBILIARIA conforme al Codigo Civil y Comercial de la Nacion (arts. 1170 a 1185) y las clausulas que siguen:`
  y = parrafo(doc, y, intro)

  y = bloqueParte(doc, y, 'VENDEDOR/A', clienteCompleto(propietario))
  y = bloqueParte(doc, y, 'COMPRADOR/A', clienteCompleto(inquilino))

  y = clausulaTitulo(doc, y, 'PRIMERO', 'Objeto')
  y = parrafo(doc, y, `EL/LA VENDEDOR/A vende y EL/LA COMPRADOR/A compra, libre de toda deuda, gravamen, embargo, inhibicion u ocupante, el inmueble ubicado en ${propiedad?.direccion || 'a completar'}, ${ciudadOp}, Pcia. de ${provinciaOp}, con una superficie aproximada de ${propiedad?.superficie_m2 || 0} m2. La identificacion catastral, partida inmobiliaria y matricula registral se completaran en la escritura traslativa de dominio.`)

  y = clausulaTitulo(doc, y, 'SEGUNDO', 'Precio total y forma de pago')
  y = parrafo(doc, y, `El precio total y definitivo de la operacion se fija en ${fmtMoneda(contrato.monto_inicial)}, que sera abonado por EL/LA COMPRADOR/A al/a la VENDEDOR/A de la siguiente forma: (a) la suma de ${fmtMoneda(contrato.deposito)} en concepto de SENA y a cuenta del precio, abonada en este acto, sirviendo el presente como recibo y carta de pago; (b) el saldo restante sera abonado en oportunidad de la firma de la escritura traslativa de dominio.`)

  y = clausulaTitulo(doc, y, 'TERCERO', 'Sena - principio de ejecucion')
  y = parrafo(doc, y, 'La sena entregada en este acto reviste el caracter de PRINCIPIO DE EJECUCION del contrato, conforme art. 1059 del CCyC, no funcionando como sena penitencial. En consecuencia, ninguna de las partes podra retractarse, salvo lo dispuesto en la clausula penal.')

  y = clausulaTitulo(doc, y, 'CUARTO', 'Escritura traslativa')
  y = parrafo(doc, y, `Las partes acuerdan que la escritura publica traslativa de dominio se otorgara dentro del plazo que vence el ${fmtFecha(contrato.fecha_fin)}, ante el escribano que designe EL/LA COMPRADOR/A. EL/LA VENDEDOR/A se obliga a presentar la totalidad de la documentacion necesaria: titulos, planos, libre deuda de impuestos, expensas y servicios. Los gastos de escrituracion seran soportados conforme uso y costumbre de plaza.`)

  y = clausulaTitulo(doc, y, 'QUINTO', 'Posesion')
  y = parrafo(doc, y, 'La posesion del inmueble se entregara al/a la COMPRADOR/A libre de ocupantes, muebles y enseres, en oportunidad de la firma de la escritura traslativa y previo pago integro del saldo del precio. Hasta dicho momento, el inmueble permanecera en poder del/de la VENDEDOR/A, responsable por su conservacion.')

  y = clausulaTitulo(doc, y, 'SEXTO', 'Estado del inmueble')
  y = parrafo(doc, y, 'EL/LA COMPRADOR/A declara conocer y aceptar el estado actual de conservacion del inmueble, manifestando que la operacion se realiza en el estado en que el bien se encuentra al dia de la fecha. EL/LA VENDEDOR/A garantiza encontrarse en plena posesion del inmueble, libre de toda restriccion de dominio, embargo, inhibicion, hipoteca o gravamen.')

  y = clausulaTitulo(doc, y, 'SEPTIMO', 'Clausula penal')
  y = parrafo(doc, y, 'Para el supuesto de incumplimiento de cualquiera de las partes, la parte cumplidora podra optar entre: (a) demandar el cumplimiento forzado del contrato; o (b) resolver el contrato y reclamar a la parte incumplidora una multa equivalente al CIEN POR CIENTO (100%) de la sena entregada, sin perjuicio de las indemnizaciones por danos y perjuicios que correspondieran.')

  y = clausulaTitulo(doc, y, 'OCTAVO', 'Comision inmobiliaria')
  y = parrafo(doc, y, `Las partes reconocen que la operacion ha sido gestionada por ${EMPRESA.nombre} en su calidad de inmobiliaria intermediaria, con domicilio comercial en ${EMPRESA.domicilio_comercial}, ${EMPRESA.ciudad}, comprometiendose cada parte al pago de la comision pactada del ${contrato.comision_porc || 3}% sobre el precio total de la operacion, conforme uso y costumbre de plaza, pagadera al momento de la escritura.`)

  y = clausulaTitulo(doc, y, 'NOVENO', 'Domicilios y jurisdiccion')
  y = parrafo(doc, y, `Las partes constituyen domicilios especiales en los indicados precedentemente. Para toda divergencia derivada del presente, se someten a ${EMPRESA.jurisdiccion}, con renuncia a todo otro fuero o jurisdiccion.`)

  if (contrato.notas) {
    y = clausulaTitulo(doc, y, 'NOTAS ADICIONALES', '')
    y = parrafo(doc, y, contrato.notas)
  }

  if (y > H - 80) doc.addPage()
  firmasDoble(doc, 'VENDEDOR/A', 'COMPRADOR/A')
  footer(doc, codigo)
  doc.save(`${codigo}-boleto-compraventa.pdf`)
}

// ──────────── entrada publica ────────────

export function generarPDFContrato(args) {
  const tipo = args?.contrato?.tipo
  if (tipo === 'alquiler_comercial') return pdfAlquilerComercial(args)
  if (tipo === 'boleto_compraventa') return pdfBoletoCompraventa(args)
  return pdfAlquilerVivienda(args)
}
