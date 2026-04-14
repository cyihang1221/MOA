function L = del_lines(L,x,y,lim)
%Magnus Åberg

dx = x(L(:,1))-x(L(:,2));
dy = y(L(:,1))-y(L(:,2));

d = sqrt(dx.^2 + dy.^2);
L(d>lim,:) = [];
%fprintf(1,'del_lines: %i lines deleted.\n',sum(d>lim))

