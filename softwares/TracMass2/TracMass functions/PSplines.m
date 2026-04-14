function GCV=PSplines( y, B, pord, L,softness)
%by: Magnus Åberg
L=min(-10,L);
L=max(10,L);


[~, GCV]=fitPSplines( y, B, pord, 10^L);
GCV=GCV+softness*(L/10)^2;