open Bioc_wire
module B=Archive_budget
type diagnostic_profile=Python311|Python314
type entry=string*string
type member={path:string;byte_length:int;sha256:string}
let require value message=Diagnostic.require value "archive_container" message
let invalid message=Diagnostic.fail "archive_container"("Invalid reference archive: "^message)
let count budget maximum values=
  let rec loop number=function []->number |_::tail->B.charge budget 1;
    require(number<maximum)"Archive member count exceeds the limit.";loop(number+1)tail in loop 0 values
let safe_path budget path=
  B.guard budget;
  require(path<>"")"Archive member path must be text.";
  B.product budget(String.length path+1)4;
  let canonical=ref(path.[0]<>'/') and segment=ref 0 in
  let part stop=let length=stop- !segment in
    if length=0 || (length=1 && path.[!segment]='.') ||
      (length=2 && path.[!segment]='.' && path.[!segment+1]='.') then canonical:=false in
  String.iteri(fun index character->
    if character='\\' || character=':' || Char.code character<32 || Char.code character=127 then canonical:=false;
    if character='/' then (part index;segment:=index+1))path;
  part(String.length path);
  require !canonical "Archive member paths must be canonical relative POSIX files.";
  (try Json.validate_utf8 path with Diagnostic.Error error when error.code="invalid_utf8"->
    Diagnostic.fail "archive_container" "Archive member path is not valid UTF-8.");
  require(String.length path<=(B.limits budget).max_path_bytes)"Archive member path is too long."
let reserved path=path="manifest.json" || path="run.json"
let equal budget left right=B.charge budget(String.length left+String.length right+1);left=right
let member_key budget key values=List.find_opt(fun(path,_)->equal budget key path)values
let validate_files budget members files=
  B.guard budget;
  ignore(count budget (B.limits budget).max_json_nodes members);
  let expected=List.fold_left(fun values declaration->
    require(Option.is_none(member_key budget declaration.path values))"Duplicate manifest member paths.";
    B.reserve budget 64;(declaration.path,declaration)::values)[] members in
  ignore(count budget (B.limits budget).max_json_nodes files);
  let total=ref 0 and actual=ref [] in
  List.iter(fun(path,payload)->safe_path budget path;
    require(not(reserved path))"Package payload cannot replace archive metadata.";
    require(String.length payload<=(B.limits budget).max_member_bytes)"Archive member exceeds the size limit.";
    total:= !total+String.length payload;
    require(!total<=(B.limits budget).max_archive_bytes)"Archive payload exceeds the total size limit.";
    require(Option.is_none(member_key budget path !actual))"Duplicate archive member path.";
    B.reserve budget(String.length path+String.length payload+64);actual:=(path,payload)::!actual)files;
  require(List.length !actual=List.length expected &&
    List.for_all(fun(path,_)->Option.is_some(member_key budget path expected))!actual)
    "Archive file inventory differs from the manifest.";
  List.iter(fun(path,payload)->let declared=snd(Option.get(member_key budget path expected)) in
    let matches=String.length payload=declared.byte_length &&
      (B.charge budget(String.length payload+1);Canonical.sha256 payload=declared.sha256) in
    require matches("Archive member size or SHA-256 mismatch: "^path^"."))files;
  files
let crc budget data offset length=
  B.product budget(length+1)10;
  let value=ref Int32.minus_one in
  for index=offset to offset+length-1 do
    value:=Int32.logxor !value(Int32.of_int(Char.code data.[index]));
    for _=1 to 8 do value:=Int32.logxor(Int32.shift_right_logical !value 1)
      (if Int32.logand !value 1l=0l then 0l else 0xedb88320l) done
  done;Int32.lognot !value
let u16 text offset=Char.code text.[offset] lor(Char.code text.[offset+1] lsl 8)
let u32 text offset=u16 text offset lor(u16 text(offset+2) lsl 16)
let crc_int value=Int64.to_int(Int64.logand(Int64.of_int32 value)0xffffffffL)
let sorted budget values=
  let n=count budget (B.limits budget).max_entries values in
  let names=List.fold_left(fun total(name,_)->B.charge budget 1;total+String.length name)0 values in
  B.product budget(n+names+1)40;B.reserve budget(128*n+1024);
  List.sort(fun(a,_)(b,_)->String.compare a b)values
let encode budget entries=
  B.guard budget;
  let controls=B.limits budget in
  let n=count budget controls.max_entries entries in require(n>0)"Archive member count exceeds the limit.";
  let total=List.fold_left(fun total(_,value)->B.charge budget 1;
    require(String.length value<=controls.max_archive_bytes-total)"Archive contents exceed the total size limit.";
    total+String.length value)0 entries in
  let metadata=ref 22 in
  List.iter(fun(name,_)->safe_path budget name;metadata:= !metadata+76+2*String.length name)entries;
  require(total<=controls.max_archive_bytes- !metadata)"Archive exceeds the byte-size limit.";
  let entries=sorted budget entries and previous=ref None in
  List.iter(fun(name,_)->require(!previous<>Some name)"Duplicate archive member path.";previous:=Some name)entries;
  let length=total+ !metadata in B.product budget length 3;B.reserve budget(length+128+128*n);
  let output=Bytes.create length and cursor=ref 0 in
  let put text=Bytes.blit_string text 0 output !cursor(String.length text);cursor:= !cursor+String.length text in
  let number width value=for index=0 to width-1 do Bytes.set output(!cursor+index)(Char.chr((value lsr(8*index))land 255))done;
    cursor:= !cursor+width in
  let rows=List.map(fun(name,payload)->
    let offset= !cursor and size=String.length payload in
    let flag=if String.exists(fun value->Char.code value>=128)name then 0x800 else 0 in
    let checksum=crc_int(crc budget payload 0 size) in
    put "PK\003\004";number 2 20;number 2 flag;number 2 0;number 2 0;number 2 33;
    number 4 checksum;number 4 size;number 4 size;number 2(String.length name);number 2 0;put name;put payload;
    name,size,flag,checksum,offset)entries in
  let directory= !cursor in
  List.iter(fun(name,size,flag,checksum,offset)->
    put "PK\001\002";number 2 0x0314;number 2 20;number 2 flag;number 2 0;number 2 0;number 2 33;
    number 4 checksum;number 4 size;number 4 size;number 2(String.length name);
    number 2 0;number 2 0;number 2 0;number 2 0;number 4 0x81a40000;number 4 offset;put name)rows;
  let directory_size= !cursor-directory in
  put "PK\005\006";number 2 0;number 2 0;number 2 n;number 2 n;number 4 directory_size;number 4 directory;number 2 0;
  Diagnostic.require(!cursor=length)"archive_encoding" "Archive output preflight differs.";
  Bytes.unsafe_to_string output
let assemble budget ~manifest ~members ~files ?run_metadata ()=
  let entries=validate_files budget members files in
  (* Original metadata size check follows both complete serializations. The
     wider archive byte cap bounds those allocations before that semantic check. *)
  let controls=B.limits budget in
  let manifest=Utf8_pretty.encode budget ~max_bytes:controls.max_archive_bytes manifest in
  let run=Option.map(Utf8_pretty.encode budget ~max_bytes:controls.max_archive_bytes)run_metadata in
  require(String.length manifest<=controls.max_metadata_bytes &&
    Option.fold ~none:true ~some:(fun raw->String.length raw<=controls.max_metadata_bytes)run)
    "Archive metadata exceeds the size limit.";
  let entries=("manifest.json",manifest)::entries in
  encode budget(match run with None->entries|Some value->("run.json",value)::entries)
let add_codepoint output scalar=
  let byte n=Buffer.add_char output(Char.chr n) in
  if scalar<128 then byte scalar else if scalar<2048 then (byte(0xc0 lor(scalar lsr 6));byte(0x80 lor(scalar land 63)))
  else if scalar<65536 then (byte(0xe0 lor(scalar lsr 12));byte(0x80 lor((scalar lsr 6)land 63));byte(0x80 lor(scalar land 63)))
  else (byte(0xf0 lor(scalar lsr 18));byte(0x80 lor((scalar lsr 12)land 63));byte(0x80 lor((scalar lsr 6)land 63));byte(0x80 lor(scalar land 63)))
let utf8 budget text=
  B.product budget(String.length text+1)4;
  let n=String.length text in
  let failure first last reason=
    let location=if last=first+1 then Printf.sprintf "byte 0x%02x in position %d"(Char.code text.[first])first
      else Printf.sprintf "bytes in position %d-%d" first(last-1) in
    invalid("'utf-8' codec can't decode "^location^": "^reason) in
  let rec walk index=if index<n then begin
    let first=Char.code text.[index] in
    let width=if first<128 then 1 else if first>=194 && first<=223 then 2
      else if first>=224 && first<=239 then 3 else if first>=240 && first<=244 then 4
      else failure index(index+1)"invalid start byte" in
    for step=1 to width-1 do
      if index+step>=n then failure index n "unexpected end of data";
      let value=Char.code text.[index+step] in
      if value<128 || value>191 || (step=1 && ((first=224 && value<160)||(first=237 && value>=160)||
          (first=240 && value<144)||(first=244 && value>=144))) then
        failure index(index+step)"invalid continuation byte"
    done;walk(index+width)
  end in walk 0;text
let decode_name budget flags bytes=
  if flags land 0x800<>0 then utf8 budget bytes else begin
    B.product budget(String.length bytes+1)4;B.reserve budget(6*String.length bytes+64);
    let output=Buffer.create(3*String.length bytes) in
    String.iter(fun byte->add_codepoint output (Archive_unicode.decode_cp437(Char.code byte)))bytes;Buffer.contents output
  end
let scalars text emit=
  let byte i=Char.code text.[i] in
  let rec loop i=if i<String.length text then begin
    let first=byte i in
    let scalar,width=if first<128 then first,1 else if first<224 then ((first land 31)lsl 6)lor(byte(i+1)land 63),2
      else if first<240 then ((first land 15)lsl 12)lor((byte(i+1)land 63)lsl 6)lor(byte(i+2)land 63),3
      else ((first land 7)lsl 18)lor((byte(i+1)land 63)lsl 12)lor((byte(i+2)land 63)lsl 6)lor(byte(i+3)land 63),4 in
    emit scalar i width;loop(i+width)
  end in loop 0
let printable profile scalar=match profile with
  |Python311->Archive_unicode.printable311 scalar|Python314->Archive_unicode.printable314 scalar
let repr budget profile ~bytes text=
  B.product budget(String.length text+1)32;B.reserve budget(12*String.length text+64);
  let output=Buffer.create(6*String.length text+2) in
  let quote=if String.contains text '\'' && not(String.contains text '"') then '"' else '\'' in
  if bytes then Buffer.add_char output 'b';Buffer.add_char output quote;
  let emit scalar offset width=
    if scalar=Char.code quote || scalar=92 then (Buffer.add_char output '\\';Buffer.add_char output(Char.chr scalar))
    else match scalar with
      |9->Buffer.add_string output "\\t"|10->Buffer.add_string output "\\n"|13->Buffer.add_string output "\\r"
      |n when (bytes && (n<32 || n>=127)) || (not bytes && not(printable profile n))->
        Buffer.add_string output(Printf.sprintf(if n<=255 then "\\x%02x" else if n<=65535 then "\\u%04x" else "\\U%08x")n)
      |_->Buffer.add_substring output text offset width in
  if bytes then String.iteri(fun i c->emit(Char.code c)i 1)text else scalars text emit;
  Buffer.add_char output quote;Buffer.contents output
let slice budget data offset length=
  B.charge budget(length+1);B.reserve budget(length+32);String.sub data offset length
let signature data offset value=offset>=0 && offset<=String.length data-4 &&
  data.[offset]=value.[0] && data.[offset+1]=value.[1] && data.[offset+2]=value.[2] && data.[offset+3]=value.[3]
type directory={name:string;original:string;offset:int;system:int;flags:int;
  method_:int;time:int;date:int;checksum:int;compressed:int;size:int;internal:int;external_:int;decorated:bool;ordinal:int}
let nonnegative64 budget data offset=
  B.charge budget 32;B.reserve budget 64;
  Z.logor(Z.of_int(u32 data offset))(Z.shift_left(Z.of_int(u32 data(offset+4)))32)
let bounded_integer value=if Z.fits_int value then Z.to_int value else max_int
let truncate_name budget value=match String.index_opt value '\000' with
  |None->value|Some size->slice budget value 0 size
let effective_directory budget data outer_offset outer_size=
  let size=String.length data in
  if not(signature data(size-42)"PK\006\007") then outer_offset,outer_size,0
  else begin
    let locator=size-42 and fallback=size-98 in B.charge budget 76;
    if u32 data(locator+4)<>0 || u32 data(locator+16)>1 then
      invalid "zipfiles that span multiple disks are not supported";
    let relative=nonnegative64 budget data(locator+8) in
    if Z.compare relative(Z.of_int fallback)>0 then invalid "Corrupt zip64 end of central directory locator";
    let relative=Z.to_int relative in
    let at=if signature data relative "PK\006\006" then relative else fallback in
    if not(signature data at "PK\006\006") then invalid "Zip64 end of central directory record not found";
    let extra=if at=relative then fallback-relative else 0 in
    let length=nonnegative64 budget data(at+4)
    and directory_size=nonnegative64 budget data(at+40)
    and directory_offset=nonnegative64 budget data(at+48) in
    if not(Z.equal(Z.add directory_offset directory_size)(Z.of_int relative)) ||
       not(Z.equal(Z.add length(Z.of_int 12))(Z.of_int(56+extra))) then
      invalid "Corrupt zip64 end of central directory record";
    (* The nonnegative sum equality independently proves both fields fit inside
       the already bounded input. No claimed ZIP64 size drives an allocation. *)
    let length=Z.to_int directory_size and location=fallback-extra in
    location-length,length,location-relative
  end
let directory_rows budget profile data ~offset ~length ~concat=
  let ending=offset+length and cursor=ref offset and ordinal=ref 0 and rows=ref [] in
  let controls=B.limits budget in
  while !cursor<ending do
    B.charge budget 46;
    Diagnostic.require(!ordinal<controls.max_json_nodes) "archive_directory_limit"
      "ZIP directory traversal exceeds its bounded native item inventory.";
    if ending- !cursor<46 then invalid "Truncated central directory";
    let at= !cursor in
    if not(signature data at "PK\001\002")then invalid "Bad magic number for central directory";
    let flags=u16 data(at+8) and names=u16 data(at+28) and extra_size=u16 data(at+30)
    and comment_size=u16 data(at+32) in
    let position=ref(at+46) in
    let take amount=let size=min amount(ending- !position) in
      let value=slice budget data !position size in position:= !position+size;value in
    let raw=take names in
    let original=decode_name budget flags raw in
    let name=ref(truncate_name budget original) in
    let extra=take extra_size in let comment=take comment_size in
    let version=Char.code data.[at+6] in
    if version>63 then invalid(Printf.sprintf "zip file version %d.%d"(version/10)(version mod 10));
    B.reserve budget 192;
    let file_size=ref(Z.of_int(u32 data(at+24))) and compressed=ref(Z.of_int(u32 data(at+20)))
    and local_offset=ref(Z.of_int(u32 data(at+42))) in
    let extra_at=ref 0 in
    while String.length extra- !extra_at>=4 do
      B.charge budget 4;B.reserve budget 128;
      let kind=u16 extra !extra_at and size=u16 extra(!extra_at+2) in
      if size>String.length extra- !extra_at-4 then
        invalid(Printf.sprintf "Corrupt extra field %04x (size=%d)" kind size);
      let first= !extra_at+4 in
      if kind=1 then begin
        let position=ref first and stop=first+size in
        let read field target predicate=
          if predicate !target then begin
            if stop- !position<8 then invalid("Corrupt zip64 extra field. "^field^" not found.");
            target:=nonnegative64 budget extra !position;position:= !position+8
          end in
        let sentinel value=Z.equal value(Z.of_int 0xffffffff) in
        read "File size" file_size(fun value->sentinel value || Z.equal value(Z.pred(Z.shift_left Z.one 64)));
        read "Compress size" compressed sentinel;read "Header offset" local_offset sentinel
      end else if kind=0x7075 && profile=Python314 then begin
        if size<5 then invalid "Corrupt unicode path extra field (0x7075)";
        if Char.code extra.[first]=1 && u32 extra(first+1)=crc_int(crc budget raw 0(String.length raw)) then begin
          let unicode=slice budget extra(first+5)(size-5) in
          let unicode=try utf8 budget unicode with Diagnostic.Error error when error.code="archive_container"->
            invalid "Corrupt unicode path extra field (0x7075): invalid utf-8 bytes" in
          if unicode<>"" then name:=truncate_name budget unicode
        end
      end;
      extra_at:=first+size
    done;
    if !ordinal<controls.max_entries then begin
      B.reserve budget 192;
      let row={name= !name;original;offset=bounded_integer(Z.add !local_offset(Z.of_int concat));
        system=Char.code data.[at+5];flags;method_=u16 data(at+10);time=u16 data(at+12);date=u16 data(at+14);
        checksum=u32 data(at+16);compressed=bounded_integer !compressed;size=bounded_integer !file_size;
        internal=u16 data(at+36);external_=u32 data(at+38);decorated=(extra<>"" || comment<>"");ordinal= !ordinal} in
      rows:=row::!rows
    end;
    incr ordinal;cursor:=at+46+names+extra_size+comment_size
  done;
  require(!ordinal>0 && !ordinal<=controls.max_entries) "Archive member count exceeds the limit.";
  B.reserve budget(32* !ordinal);List.rev !rows
let read budget ?(diagnostics=Python314) data=
  B.guard budget;
  let controls=B.limits budget and size=String.length data in
  require(size>=22 && size<=controls.max_archive_bytes)"Archive is empty or exceeds the byte-size limit.";
  B.reserve budget(size+128);B.charge budget 22;
  let footer=size-22 in
  let number=u16 data(footer+10) and directory_size=u32 data(footer+12) and directory_offset=u32 data(footer+16) in
  require(signature data footer "PK\005\006" && u16 data(footer+4)=0 && u16 data(footer+6)=0 &&
    u16 data(footer+20)=0 && u16 data(footer+8)=number && number>0 && number<=controls.max_entries)
    "Unsupported ZIP footer, comment, disk layout or member count.";
  require(directory_offset+directory_size=footer)"ZIP has trailing data or an invalid directory.";
  let cursor=ref directory_offset in
  for _=1 to number do
    B.charge budget 46;
    require(!cursor+46<=footer && signature data !cursor "PK\001\002")"Invalid ZIP member directory.";
    let names=u16 data(!cursor+28) in
    require(names>0 && names<=controls.max_path_bytes && u16 data(!cursor+30)=0 && u16 data(!cursor+32)=0)
      "Unsupported ZIP member name, extra data or comment.";
    cursor:= !cursor+46+names;require(!cursor<=footer)"ZIP member directory is truncated."
  done;
  require(!cursor=footer)"ZIP directory member count is inconsistent.";
  (* The original preflight remains authoritative. A forged locator hidden in
     its filename may still redirect stdlib directory parsing; follow that
     bounded branch so malformed errors retain their actual source order. *)
  let directory_offset,directory_size,concat=effective_directory budget data directory_offset directory_size in
  let rows=directory_rows budget diagnostics data ~offset:directory_offset ~length:directory_size ~concat in
  let number=List.length rows in
  B.product budget number 40;B.reserve budget(128*number+1024);
  let offsets=List.stable_sort(fun left right->
    let ordering=compare left.offset right.offset in
    if ordering<>0 || diagnostics=Python314 then ordering else compare right.ordinal left.ordinal)rows in
  let next_end row=
    let rec find=function []->directory_offset|head::tail->B.charge budget 1;
      if head.ordinal=row.ordinal then (match tail with []->directory_offset|next::_->next.offset)else find tail in find offsets in
  let entries=ref [] and total=ref 0 in
  List.iter(fun row->
    safe_path budget row.name;
    require(Option.is_none(member_key budget row.name !entries))"Duplicate archive member path.";
    require(row.original=row.name && row.system=3 && row.external_=0x81a40000 && row.internal=0)
      "Archive members must be regular, non-executable files.";
    require(row.method_=0 && row.compressed=row.size && (row.flags=0 || row.flags=0x800) && row.time=0 && row.date=33 && not row.decorated)
      "Archive member violates the canonical stored-ZIP policy.";
    let maximum=if reserved row.name then controls.max_metadata_bytes else controls.max_member_bytes in
    require(row.size<=maximum)"Archive member exceeds the size limit.";
    total:= !total+row.size;require(!total<=controls.max_archive_bytes)"Archive contents exceed the total size limit.";
    let at=row.offset in B.charge budget 30;
    if at>size-30 then invalid "Truncated file header";
    if not(signature data at "PK\003\004")then invalid "Bad magic number for file header";
    let n=u16 data(at+26) and extra=u16 data(at+28) in
    let raw=slice budget data(at+30)(min n(size-at-30)) in
    let decoded=decode_name budget(u16 data(at+6))raw in
    if decoded<>row.original then invalid("File name in directory "^repr budget diagnostics ~bytes:false row.original^
      " and header "^repr budget diagnostics ~bytes:true raw^" differ.");
    let start=at+30+n+extra and stop=next_end row in
    if start+row.compressed>stop && not(diagnostics=Python314 && stop=at) then
      invalid("Overlapped entries: "^repr budget diagnostics ~bytes:false row.original^" (possible zip bomb)");
    if row.size>0 && row.size>size-start then invalid "";
    let checksum=crc_int(crc budget data start row.size) in
    if checksum<>row.checksum then invalid("Bad CRC-32 for file "^repr budget diagnostics ~bytes:false row.name);
    let payload=slice budget data (if row.size=0 then 0 else start) row.size in
    B.reserve budget 64;entries:=(row.name,payload)::!entries)rows;
  B.reserve budget(32*number);let entries=List.rev !entries in
  let canonical=encode budget entries in B.charge budget(String.length canonical+size+1);
  require(canonical=data)"Archive bytes violate canonical container encoding.";entries
