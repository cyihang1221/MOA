function Lambda=minimizeGCV( y, B, pord,softness)
%Magnus Åberg

fcn=@(L)PSplines( y, B, pord,L,softness);
Lambda=fminsearch(fcn,1);