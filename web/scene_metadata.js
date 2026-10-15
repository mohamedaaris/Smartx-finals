// Convert a point on the joined display mesh back to a named source object.
// Bounds come from warehouse1.blend and remain independent of GLB mesh merging.
export function sourceAt(point, objects) {
  let best=null, size=Infinity;
  for(const [name,x0,y0,z0,x1,y1,z1] of objects){
    if(point.x<x0-.025||point.x>x1+.025||point.y<y0-.025||point.y>y1+.025||point.z<z0-.025||point.z>z1+.025)continue;
    const volume=Math.max(.001,x1-x0)*Math.max(.001,y1-y0)*Math.max(.001,z1-z0);
    if(volume<size){best=name;size=volume}
  }
  return best;
}

export function rackAt(x,y) {
  const columns=[[-13.99,-12.08,'A'],[-5.77,-3.56,'B'],[3.10,5.02,'C']];
  const rows=[[-2.56,3.65,1],[-14.73,-8.52,2],[-27.07,-20.87,3],[-39.96,-33.76,4]];
  const col=columns.find(([a,b])=>x>=a-.25&&x<=b+.25);
  const row=rows.find(([a,b])=>y>=a-.25&&y<=b+.25);
  return col&&row?`${col[2]}R${row[2]}`:null;
}

export function floorArea(x,y) {
  if(x>=-18.18&&x<=9.01&&y>=-49.40&&y<=-43.57)return {name:'Charging / depot area',detail:'Shared charging floor with five AMR depot positions'};
  if(y>=-40.2&&y<=3.9){
    const aisles=[[-12.08,-5.77,'A'],[-3.56,3.10,'B'],[5.02,9.04,'C']];
    const aisle=aisles.find(([a,b])=>x>=a&&x<=b);
    if(aisle){
      const row=[.55,-11.62,-23.97,-36.86].reduce((best,v,i,a)=>Math.abs(y-v)<Math.abs(y-a[best])?i:best,0)+1;
      return {name:`Aisle ${aisle[2]}`,detail:`Near shelf row ${row}`,destination:`${aisle[2]}R${row}`};
    }
    const cross=[[-8.52,-2.56,'North cross aisle'],[-20.87,-14.73,'Middle cross aisle'],[-33.76,-27.07,'South cross aisle']].find(([a,b])=>y>=a&&y<=b);
    if(cross)return {name:cross[2],detail:'Shared cross aisle; passage is reservation controlled'};
  }
  if(x>=-18.14&&x<=-10.94&&y>=8.02&&y<=13.86)return {name:'Pickup area',detail:'Package intake',destination:'PICKUP'};
  if(x>=1.10&&x<=9&&y>=8.02&&y<=13.86)return {name:'Delivery area',detail:'Outbound dispatch',destination:'DELIVERY'};
  if(x>=-18.14&&x<=-10.94&&y>=-49.40&&y<=-43.57)return {name:'Charging area',detail:'AMR charging bays'};
  return {name:'Open floor',detail:'No named operational aisle at this point'};
}
